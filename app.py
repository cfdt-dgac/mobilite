#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — Application Flask CFDT Mobilité
Tableau de bord local pour gérer les campagnes de mobilité DGAC.
"""

import json
import os
import pickle
import secrets
import sys
from pathlib import Path

from flask import (Flask, abort, jsonify, redirect, render_template,
                   request, send_file, send_from_directory, url_for)

# Ajouter le dossier courant au path pour les imports
sys.path.insert(0, str(Path(__file__).parent))

from modules.extract_ave       import extract_ave_pdf
from modules.extract_resultats import extract_resultats_pdf
from modules.extract_additif   import extract_additif_pdf
from modules.process_data      import (merge_ave_resultats, apply_additif,
                                        normalize_statut,
                                        stats_par_corps, stats_par_grand_service)
from modules.scrap_csp         import scrape_csp_background, get_scrape_state
from modules.import_sirh       import load_sirh_json, sirh_stats
from modules.generate_site     import generate_static_site
from modules.generate_reports  import (report_par_grand_service,
                                        report_par_corps, report_vacants)
from modules.netlify_deploy    import deploy, check_token, get_sites, NetlifyError
from modules.secret_store      import save_token, load_token, has_token, SecretError
from modules.campaign_info     import (load_info, save_info,
                                        parse_contacts, parse_notes)
from modules.archives          import (archive_from, read_json, list_archives, archive_dir,
                                        vacants_history, history_excel)

# ── Chemins ───────────────────────────────────────────────────────────────────

BASE      = Path(__file__).parent
CONFIG_F  = BASE / "config.json"      # réglages partagés (aucun secret)
TOKEN_F   = BASE / "publication.enc"  # token Netlify chiffré par le mot de passe de publication


def _data_dir() -> Path:
    """Dossier des données de campagne : celui choisi dans Paramètres
    (ex. un dossier OneDrive partagé), sinon data/ à côté de l'appli."""
    try:
        raw = CONFIG_F.read_bytes()
        try:
            d = json.loads(raw.decode("utf-8")).get("data_dir", "").strip()
        except UnicodeDecodeError:
            d = json.loads(raw.decode("cp1252")).get("data_dir", "").strip()
        if d:
            return Path(os.path.expandvars(d)).expanduser()
    except Exception:
        pass
    return BASE / "data"


DATA      = _data_dir()
UPLOADS   = DATA / "uploads"
PROCESSED = DATA / "processed"
SITE_OUT  = DATA / "site"
REPORTS   = DATA / "reports"
STATE_F   = DATA / "state.json"
LOCK_F    = DATA / "en_cours_utilisation.json"
INFO_F    = DATA / "campaign_info.json"

for d in [UPLOADS, PROCESSED, SITE_OUT, REPORTS]:
    d.mkdir(parents=True, exist_ok=True)

# Feuille de style du site public (embarquée dans l'appli)
_CSS_SRC = BASE / "static" / "site_styles.css"

# ── Flask ─────────────────────────────────────────────────────────────────────

app = Flask(__name__)
# Clé aléatoire à chaque lancement (appli locale, pas de session à conserver)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)


# ── État persistant ───────────────────────────────────────────────────────────

def load_state() -> dict:
    default = {
        "campaign":    "",
        "step1_done":  False,
        "step2_done":  False,
        "step3_done":  False,
        "ave_count":   0,
        "csp_count":   0,
        "res_count":   0,
        "last_deploy":  "",
        "sirh_count":   0,
        "sirh_done":    False,
    }
    if STATE_F.exists():
        try:
            return {**default, **read_json(STATE_F)}
        except Exception:
            pass
    return default


def save_state(state: dict) -> None:
    STATE_F.parent.mkdir(parents=True, exist_ok=True)
    STATE_F.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> dict:
    # « netlify_token » n'est plus utilisé : il n'existe que dans les anciens
    # config.json (en clair) et disparaît dès que le token est chiffré.
    default = {"netlify_site_id": "", "organismes": "417,417-390,13781"}
    if CONFIG_F.exists():
        try:
            return {**default, **read_json(CONFIG_F)}
        except Exception:
            pass
    return default


def save_config(cfg: dict) -> None:
    CONFIG_F.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Verrou : qui travaille sur la campagne (dossier partagé) ────────────────

import getpass, socket, time as _time
_ME = f"{getpass.getuser()} sur {socket.gethostname()}"
LOCK_TTL = 2 * 3600   # un verrou sans activité depuis 2 h est considéré comme abandonné


def _read_lock() -> dict | None:
    try:
        return json.loads(LOCK_F.read_text(encoding="utf-8"))
    except Exception:
        return None


def _touch_lock() -> None:
    try:
        LOCK_F.write_text(json.dumps({"qui": _ME, "depuis": _time.strftime("%d/%m/%Y %H:%M"),
                                      "ts": _time.time()}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def other_user() -> dict | None:
    """Renvoie le verrou d'une AUTRE personne s'il est récent, sinon None."""
    lk = _read_lock()
    if lk and lk.get("qui") != _ME and _time.time() - float(lk.get("ts", 0)) < LOCK_TTL:
        return lk
    return None


@app.before_request
def _lock_heartbeat():
    # On ne prend pas la main tant qu'une autre personne travaille (sauf "Prendre la main")
    if request.endpoint in ("static",) or other_user():
        return
    _touch_lock()


@app.before_request
def _archive_outdated():
    # Toute nouvelle donnée importée rend l'archive précédente incomplète
    if request.method == "POST" and request.endpoint in (
            "upload_ave", "upload_additif", "upload_sirh", "upload_resultats"):
        st = load_state()
        if st.pop("archived", None):
            save_state(st)


@app.route("/prendre-la-main", methods=["POST"])
def take_over():
    _touch_lock()
    return redirect(url_for("index"))


# ── Sérialisation DataFrames ──────────────────────────────────────────────────

def _df_save(df, name: str) -> None:
    with open(PROCESSED / f"{name}.pkl", "wb") as f:
        pickle.dump(df, f)


def _df_load(name: str):
    p = PROCESSED / f"{name}.pkl"
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return pickle.load(f)


# ── Routes principales ────────────────────────────────────────────────────────

@app.route("/")
def index():
    state  = load_state()
    config = load_config()
    return render_template("dashboard.html", state=state, config=config,
                           other=other_user(), data_dir=str(DATA),
                           shared=(DATA != BASE / "data"))


# ── Étape 1 : Import AVE PDF ──────────────────────────────────────────────────

@app.route("/upload-ave", methods=["POST"])
def upload_ave():
    state = load_state()
    f     = request.files.get("pdf")
    camp  = request.form.get("campaign", "").strip()

    if not f or not f.filename:
        return jsonify(ok=False, msg="Aucun fichier sélectionné.")
    if not camp:
        return jsonify(ok=False, msg="Veuillez renseigner le nom de la campagne.")

    pdf_path = UPLOADS / "ave.pdf"
    f.save(str(pdf_path))

    try:
        df = extract_ave_pdf(str(pdf_path))
        if df.empty:
            return jsonify(ok=False, msg="Aucun poste extrait du PDF. Vérifiez le fichier.")
        _df_save(df, "ave")
        state["campaign"]   = camp
        state["step1_done"] = True
        state["ave_count"]  = len(df)
        # Reset des étapes suivantes si nouveau PDF
        state["step3_done"] = False
        state["res_count"]  = 0
        save_state(state)
        return jsonify(ok=True, count=len(df), campaign=camp)
    except Exception as e:
        return jsonify(ok=False, msg=f"Erreur lors de l'extraction : {e}")


# ── Étape 1b : Import PDF additif/modificatif ────────────────────────────────

@app.route("/upload-additif", methods=["POST"])
def upload_additif():
    state = load_state()
    f = request.files.get("pdf")

    if not f or not f.filename:
        return jsonify(ok=False, msg="Aucun fichier sélectionné.")

    df_ave = _df_load("ave")
    if df_ave is None:
        return jsonify(ok=False, msg="Veuillez d'abord importer le PDF AVE (étape 1).")

    # Sauvegarder le fichier avec un nom unique
    import time
    ts = int(time.time())
    pdf_path = UPLOADS / f"additif_{ts}.pdf"
    f.save(str(pdf_path))

    try:
        df_additif, date_str = extract_additif_pdf(str(pdf_path))
        if df_additif.empty:
            return jsonify(ok=False, msg="Aucune donnée extraite du PDF additif.")

        # Normaliser d'abord les "O" → "Ouvert" sur le tableau principal
        df_ave = normalize_statut(df_ave)
        # Appliquer le patch
        df_ave_patched = apply_additif(df_ave, df_additif, date_str)
        _df_save(df_ave_patched, "ave")

        # Compter fermetures et modifications
        fermes  = int(df_additif[df_additif["Statut_raw"] == "F"].shape[0])
        modifs  = int(df_additif[
            (df_additif["Statut_raw"] == "O") &
            df_additif["Type_additif"].str.contains("odificatif", na=False)
        ].shape[0])
        additifs = int(df_additif[
            (df_additif["Statut_raw"] == "O") &
            df_additif["Type_additif"].str.contains("dditif", na=False)
        ].shape[0])

        # Mémoriser la liste des additifs appliqués
        additifs_list = state.get("additifs_applied", [])
        additifs_list.append({
            "date":     date_str,
            "filename": f.filename,
            "fermes":   fermes,
            "modifs":   modifs,
            "ajouts":   additifs,
        })
        state["additifs_applied"] = additifs_list
        state["ave_count"] = len(df_ave_patched)
        save_state(state)

        return jsonify(
            ok=True,
            date=date_str,
            fermes=fermes,
            modifs=modifs,
            ajouts=additifs,
        )
    except Exception as e:
        return jsonify(ok=False, msg=f"Erreur lors de l'extraction : {e}")


# ── Étape 2 : Scraping CSP ────────────────────────────────────────────────────

@app.route("/scrape-start", methods=["POST"])
def scrape_start():
    config = load_config()
    orgs   = request.form.get("organismes", config.get("organismes", "417,417-390"))
    out    = str(PROCESSED / "offres_csp.xlsx")
    scrape_csp_background(orgs, out)
    return jsonify(ok=True)


@app.route("/scrape-status")
def scrape_status():
    st = get_scrape_state()
    # Si terminé, mettre à jour l'état global
    if st["done"] and not st["running"]:
        import pandas as pd
        state = load_state()
        try:
            df_csp = pd.read_excel(str(PROCESSED / "offres_csp.xlsx"))
            state["step2_done"] = True
            state["csp_count"]  = len(df_csp)
            save_state(state)
        except Exception:
            pass
    return jsonify(**st)


# ── Étape 2b : Import SIRH JSON ──────────────────────────────────────────────

@app.route("/upload-sirh", methods=["POST"])
def upload_sirh():
    state = load_state()
    f = request.files.get("json")

    if not f or not f.filename:
        return jsonify(ok=False, msg="Aucun fichier sélectionné.")
    if not f.filename.lower().endswith(".json"):
        return jsonify(ok=False, msg="Le fichier doit être un .json (généré par le scraper SIRH).")

    json_path = UPLOADS / "offres_sirh.json"
    f.save(str(json_path))

    try:
        df_sirh = load_sirh_json(str(json_path))
        _df_save(df_sirh, "sirh")

        stats = sirh_stats(df_sirh)
        state["sirh_done"]  = True
        state["sirh_count"] = stats["total"]
        save_state(state)

        return jsonify(
            ok=True,
            total=stats["total"],
            with_detail=stats["with_detail"],
        )
    except Exception as e:
        return jsonify(ok=False, msg=f"Erreur lors de l'import : {e}")


# ── Étape 3 : Import résultats CDM ───────────────────────────────────────────

@app.route("/upload-resultats", methods=["POST"])
def upload_resultats():
    state = load_state()
    f     = request.files.get("pdf")

    if not f or not f.filename:
        return jsonify(ok=False, msg="Aucun fichier sélectionné.")

    pdf_path = UPLOADS / "resultats.pdf"
    f.save(str(pdf_path))

    try:
        df_res = extract_resultats_pdf(str(pdf_path))
        if df_res.empty:
            return jsonify(ok=False, msg="Aucun résultat extrait du PDF.")

        df_ave = _df_load("ave")
        if df_ave is None:
            return jsonify(ok=False, msg="Veuillez d'abord importer le PDF AVE (étape 1).")

        df_complet, df_retenus, df_vacants = merge_ave_resultats(df_ave, df_res)
        _df_save(df_res,      "resultats")
        _df_save(df_complet,  "complet")
        _df_save(df_retenus,  "retenus")
        _df_save(df_vacants,  "vacants")

        state["step3_done"] = True
        state["res_count"]  = len(df_retenus)
        save_state(state)

        return jsonify(
            ok=True,
            retenus=int(len(df_retenus)),
            vacants=int(len(df_vacants)),
        )
    except Exception as e:
        return jsonify(ok=False, msg=f"Erreur lors de l'extraction : {e}")


# ── Étape 4 : Génération des sorties ─────────────────────────────────────────

@app.route("/generate-site", methods=["POST"])
def generate_site():
    import pandas as pd
    state = load_state()

    df_ave = _df_load("ave")
    if df_ave is None:
        return jsonify(ok=False, msg="Étape 1 non complétée.")

    df_csp = None
    if (PROCESSED / "offres_csp.xlsx").exists():
        try:
            df_csp = pd.read_excel(str(PROCESSED / "offres_csp.xlsx"))
        except Exception:
            pass

    df_complet = _df_load("complet")
    df_sirh    = _df_load("sirh")

    # Construction du mapping AVE → URL CSP
    import re as _re
    import unicodedata as _ud

    def _norm_title(s):
        """Normalise un intitulé pour comparaison : minuscules, sans accents, sans ponctuation."""
        s = str(s or "").lower()
        s = ''.join(c for c in _ud.normalize('NFD', s) if _ud.category(c) != 'Mn')
        s = _re.sub(r'[^a-z0-9 ]', ' ', s)
        return ' '.join(s.split())

    def _extract_ave_title(libelle):
        """Extrait le titre de base d'un libellé AVE comme '2 postes — Chef de bureau*SNA/CE'."""
        m = _re.search(r'[-—–]\s*(.+?)(?:\*|$)', str(libelle or ''))
        return _norm_title(m.group(1)) if m else _norm_title(libelle)

    ave_to_url = {}
    if df_csp is not None and "numero_ave" in df_csp.columns:
        # 1. Correspondance par numéro AVE (ancien format "DGAC-AVE-127265-CAT-A")
        for _, r in df_csp.iterrows():
            raw = str(r.get("numero_ave", "") or "")
            k = _re.sub(r'[^\d]', '', raw).lstrip("0")
            u = str(r.get("url", "") or "")
            if k and u and u.lower() != 'nan':
                ave_to_url[k] = u

        # 2. Fallback : correspondance par titre + commune (nouveau format 2026-XXXXXXX)
        if df_ave is not None and not df_csp.empty:
            # Index CSP : (titre_norm, commune_norm) → url
            csp_title_idx = {}
            for _, r in df_csp.iterrows():
                u = str(r.get("url", "") or "")
                if not u or u.lower() == 'nan':
                    continue
                titre = _norm_title(r.get("titre", ""))
                loc   = _norm_title(r.get("localisation", ""))
                # Clé par titre seul et par titre+commune
                if titre:
                    csp_title_idx.setdefault(titre, u)
                    commune_word = loc.split()[0] if loc else ""
                    if commune_word:
                        csp_title_idx.setdefault(f"{titre}|{commune_word}", u)

            for _, row in df_ave.iterrows():
                ave_num = _re.sub(r'[^\d]', '', str(row.get("N° AVE", "") or "")).lstrip("0")
                if ave_num in ave_to_url:
                    continue  # déjà trouvé
                title_norm  = _extract_ave_title(row.get("Libellé du poste", ""))
                commune_norm = _norm_title(row.get("Commune", "")).split()[0] if row.get("Commune") else ""
                # Essayer titre+commune puis titre seul
                url = csp_title_idx.get(f"{title_norm}|{commune_norm}") or csp_title_idx.get(title_norm)
                if url and ave_num:
                    ave_to_url[ave_num] = url

    assets_src = str(_CSS_SRC) if _CSS_SRC.exists() else None

    try:
        files = generate_static_site(
            df_ave     = df_ave,
            df_csp     = df_csp,
            df_complet = df_complet,
            df_sirh    = df_sirh,
            outdir     = str(SITE_OUT),
            campaign   = state.get("campaign", ""),
            ave_to_url = ave_to_url,
            assets_src = assets_src,
            info       = load_info(INFO_F),
        )
        return jsonify(ok=True, files=len(files))
    except Exception as e:
        return jsonify(ok=False, msg=str(e))


@app.route("/generate-reports", methods=["POST"])
def generate_reports():
    state      = load_state()
    df_complet = _df_load("complet")

    if df_complet is None:
        return jsonify(ok=False, msg="Étape 3 (résultats CDM) non complétée.")

    campaign = state.get("campaign", "campagne")
    try:
        p_gs  = report_par_grand_service(df_complet, campaign, str(REPORTS))
        p_c   = report_par_corps(df_complet, campaign, str(REPORTS))
        p_vac = report_vacants(df_complet, campaign, str(REPORTS))
        return jsonify(
            ok=True,
            grand_service=Path(p_gs).name,
            corps=list(p_c.keys()),
            vacants=Path(p_vac).name,
        )
    except Exception as e:
        return jsonify(ok=False, msg=str(e))


@app.route("/reports/<filename>")
def serve_report(filename):
    # send_from_directory bloque les chemins du type "..\\config.json"
    if not filename.lower().endswith(".html"):
        abort(404)
    return send_from_directory(str(REPORTS), filename)


@app.route("/list-reports")
def list_reports():
    files = [f.name for f in REPORTS.glob("*.html")]
    return jsonify(files=sorted(files))


# ── Déploiement Netlify ───────────────────────────────────────────────────────

@app.route("/deploy", methods=["POST"])
def netlify_deploy():
    config  = load_config()
    site_id = config.get("netlify_site_id", "")
    password = (request.get_json(silent=True) or {}).get("password", "")

    if has_token(TOKEN_F):
        if not password:
            return jsonify(ok=False, msg="Saisissez le mot de passe de publication.")
        try:
            token = load_token(TOKEN_F, password)
        except SecretError as e:
            return jsonify(ok=False, msg=str(e))
    else:
        # Ancien config.json avec token en clair (avant chiffrement)
        token = config.get("netlify_token", "")
        if not token:
            return jsonify(ok=False, msg="Token Netlify non configuré (Paramètres).")
    if not site_id:
        return jsonify(ok=False, msg="ID du site Netlify non configuré (Paramètres).")
    if not list(SITE_OUT.glob("*.html")):
        return jsonify(ok=False, msg="Générez d'abord le site (bouton ci-dessus).")

    try:
        url = deploy(str(SITE_OUT), site_id, token)
        state = load_state()
        state["last_deploy"] = url
        save_state(state)
        return jsonify(ok=True, url=url)
    except NetlifyError as e:
        return jsonify(ok=False, msg=str(e))
    except Exception as e:
        return jsonify(ok=False, msg=f"Erreur Netlify : {e}")


# ── Infos pratiques de la campagne (dates, contacts, notes) ─────────────────

@app.route("/campagne", methods=["GET", "POST"])
def campagne():
    msg = ""
    if request.method == "POST":
        info = save_info(INFO_F, request.form)
        msg = "Informations enregistrées. Régénérez le site (étape 4) pour les publier."
    else:
        info = load_info(INFO_F)
    _, bad_contacts = parse_contacts(info["contacts"])
    _, bad_notes    = parse_notes(info["notes"])
    return render_template("campagne.html", info=info, msg=msg,
                           state=load_state(),
                           bad_contacts=bad_contacts, bad_notes=bad_notes)


# ── Archives des campagnes et historique des postes non pourvus ─────────────

@app.route("/archiver", methods=["POST"])
def archiver():
    try:
        meta = archive_from(DATA, DATA)
        state = load_state()
        state["archived"] = meta["slug"]
        save_state(state)
        return redirect(url_for("archives", msg=f"Campagne « {meta['campaign']} » archivée."))
    except Exception as e:
        return redirect(url_for("archives", err=str(e)))


@app.route("/archives")
def archives():
    return render_template("archives.html", archives=list_archives(DATA),
                           state=load_state(), data_dir=str(DATA),
                           msg=request.args.get("msg", ""), err=request.args.get("err", ""))


@app.route("/archives/importer", methods=["POST"])
def archives_import():
    src = request.form.get("src", "").strip().strip('"')
    try:
        src_p = Path(os.path.expandvars(src)).expanduser()
        if (src_p / "data" / "state.json").exists():
            src_p = src_p / "data"
        meta = archive_from(src_p, DATA)
        return redirect(url_for("archives", msg=f"Ancienne campagne « {meta['campaign']} » importée."))
    except Exception as e:
        return redirect(url_for("archives", err=f"Import impossible : {e}"))


@app.route("/archives/<slug>/site/")
@app.route("/archives/<slug>/site/<path:p>")
def archive_site(slug, p="index.html"):
    d = archive_dir(DATA, slug)
    if d is None or not (d / "site").is_dir():
        abort(404)
    return send_from_directory(str(d / "site"), p)


@app.route("/archives/<slug>/rapports/<filename>")
def archive_report(slug, filename):
    d = archive_dir(DATA, slug)
    if d is None or not filename.lower().endswith(".html"):
        abort(404)
    return send_from_directory(str(d / "reports"), filename)


@app.route("/historique")
def historique():
    detail, rec = vacants_history(DATA)
    camps = list(dict.fromkeys(detail["Campagne"])) if not detail.empty else []
    return render_template("historique.html",
                           rec=rec.to_dict("records"), detail=detail.to_dict("records"),
                           campagnes=camps, n_multi=int((rec["Nb campagnes"] > 1).sum()) if not rec.empty else 0)


@app.route("/historique.xlsx")
def historique_xlsx():
    import tempfile
    out = Path(tempfile.gettempdir()) / "historique_postes_non_pourvus.xlsx"
    history_excel(DATA, out)
    return send_file(str(out), as_attachment=True,
                     download_name="historique_postes_non_pourvus.xlsx")


# ── Paramètres ────────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
def settings():
    config = load_config()
    msg, err = "", ""
    if request.method == "POST":
        config["netlify_site_id"] = request.form.get("netlify_site_id", "").strip()
        config["organismes"]      = request.form.get("organismes", "417,417-390").strip()
        new_dir = request.form.get("data_dir", "").strip().strip('"')
        changed = new_dir != config.get("data_dir", "")
        config["data_dir"] = new_dir

        # Nouveau token → chiffré avec le mot de passe de publication
        new_token = request.form.get("netlify_token", "").strip()
        pwd1 = request.form.get("publish_password", "")
        pwd2 = request.form.get("publish_password2", "")
        token_msg = ""
        if new_token or pwd1:
            if not new_token:
                err = "Pour changer le mot de passe, saisissez aussi le token Netlify."
            elif len(pwd1) < 8:
                err = "Le mot de passe de publication doit faire au moins 8 caractères."
            elif pwd1 != pwd2:
                err = "Les deux mots de passe ne sont pas identiques."
            else:
                try:
                    save_token(TOKEN_F, new_token, pwd1)
                    config.pop("netlify_token", None)   # plus jamais en clair
                    token_msg = " Token chiffré enregistré."
                except SecretError as e:
                    err = str(e)

        save_config(config)
        msg = "Paramètres enregistrés." + token_msg
        if err:
            msg += " Token non modifié."
        if changed:
            msg += " Dossier des données modifié : fermez puis relancez lancer.bat."

    legacy_token = config.get("netlify_token", "")
    sites = []
    if legacy_token:
        try:
            sites = get_sites(legacy_token)
        except Exception:
            pass
    return render_template("settings.html", config=config, msg=msg, err=err, sites=sites,
                           token_saved=has_token(TOKEN_F), legacy_token=bool(legacy_token),
                           data_dir=str(DATA))


@app.route("/check-token")
def check_netlify_token():
    token = request.args.get("token", "")
    ok    = check_token(token)
    sites = []
    if ok:
        try:
            sites = get_sites(token)
        except Exception:
            pass
    return jsonify(ok=ok, sites=[{"id": s["id"], "name": s["name"]} for s in sites])


# ── Reset ─────────────────────────────────────────────────────────────────────

@app.route("/reset", methods=["POST"])
def reset():
    import shutil
    for p in PROCESSED.glob("*.pkl"):
        p.unlink(missing_ok=True)
    if STATE_F.exists():
        STATE_F.unlink()
    return redirect(url_for("index"))


# ── Lancement ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  CFDT Aviation Civile — Gestion de la Mobilité")
    print("  Ouvrez votre navigateur sur : http://localhost:5000")
    print("="*55 + "\n")
    app.run(debug=False, host="127.0.0.1", port=5000)
