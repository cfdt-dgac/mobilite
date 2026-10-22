#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
archives.py
Archivage des campagnes terminées et historique des postes non pourvus.

Chaque campagne archivée est copiée dans  <dossier des données>/archives/<nom-campagne>/
avec son site statique (consultable en local), ses PDF, ses données extraites,
ses rapports, et un fichier postes_non_pourvus.xlsx.
"""

import json
import pickle
import re
import shutil
import time
import unicodedata
from pathlib import Path

import pandas as pd

ARCH_DIRS  = ["site", "processed", "uploads", "reports"]
ARCH_FILES = ["state.json", "campaign_info.json"]
HIST_COLS  = ["Grand service", "Service", "Commune", "Libellé du poste",
              "Corps et restriction", "N° AVE", "Première CDM d'ouverture du poste"]


# ── Utilitaires ───────────────────────────────────────────────────────────────

def read_json(path: Path) -> dict:
    """Lit un JSON écrit en UTF-8 ou dans l'ancien encodage Windows (cp1252)."""
    raw = Path(path).read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return json.loads(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    return json.loads(raw.decode("utf-8", errors="replace"))


def _ascii(s) -> str:
    s = str(s or "").lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def slugify(name: str) -> str:
    return re.sub(r"\s+", "-", _ascii(name))[:60] or "campagne"


def archives_root(data_dir: Path) -> Path:
    return Path(data_dir) / "archives"


def _load_pkl(p: Path):
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return pickle.load(f)


def _poste_label(libelle: str) -> str:
    """'2 postes — Chef de bureau*SNA/CE' → 'Chef de bureau'"""
    s = re.sub(r"^\s*\d+\s+postes?\s*[—–-]\s*", "", str(libelle or ""))
    return re.sub(r"\*.*$", "", s).strip()


def _commune(c: str) -> str:
    return re.sub(r"\s+CEDEX.*$", "", str(c or ""), flags=re.I).strip()


def _vacants(processed: Path) -> pd.DataFrame | None:
    """Postes non pourvus d'une campagne (hors postes fermés par additif)."""
    v = _load_pkl(processed / "vacants.pkl")
    if v is None:
        c = _load_pkl(processed / "complet.pkl")
        if c is None:
            return None
        v = c[c["Agent retenu"].fillna("") == ""]
    v = v.copy()
    ferme = v["Statut"].astype(str).str.contains("Ferm", na=False)
    if "_ferme" in v.columns:
        ferme |= v["_ferme"].fillna(False).astype(bool)
    v = v[~ferme]
    for col in HIST_COLS:
        if col not in v.columns:
            v[col] = ""
    return v[HIST_COLS].fillna("").astype(str)


# ── Archivage ─────────────────────────────────────────────────────────────────

def archive_from(src_data: Path, data_dir: Path) -> dict:
    """Archive le contenu d'un dossier data/ (campagne en cours ou ancienne campagne)."""
    src_data = Path(src_data)
    state_f = src_data / "state.json"
    if not state_f.exists():
        raise ValueError(f"Pas de fichier state.json dans {src_data} : ce n'est pas un dossier de campagne.")
    state = read_json(state_f)
    name = (state.get("campaign") or "").strip()
    if not name or not state.get("step1_done"):
        raise ValueError("Aucune campagne à archiver (l'étape 1 n'a pas été faite).")

    slug = slugify(name)
    dest = archives_root(data_dir) / slug
    if src_data.resolve() == dest.resolve() or archives_root(data_dir).resolve() in src_data.resolve().parents:
        raise ValueError("Ce dossier est déjà une archive.")
    dest.mkdir(parents=True, exist_ok=True)

    for d in ARCH_DIRS:
        if (src_data / d).is_dir():
            shutil.copytree(src_data / d, dest / d, dirs_exist_ok=True)
    for f in ARCH_FILES:
        if (src_data / f).exists():
            (dest / f).write_text(json.dumps(read_json(src_data / f), ensure_ascii=False, indent=2),
                                  encoding="utf-8")

    complet = _load_pkl(dest / "processed" / "complet.pkl")
    vac = _vacants(dest / "processed")
    if vac is not None:
        vac.to_excel(dest / "postes_non_pourvus.xlsx", index=False)

    # Date de la campagne = date d'import des résultats (à défaut, de l'AVE)
    ref = dest / "processed" / ("complet.pkl" if complet is not None else "ave.pkl")
    date_camp = time.strftime("%Y-%m-%d", time.localtime(ref.stat().st_mtime)) if ref.exists() else ""

    meta = {
        "campaign":      name,
        "slug":          slug,
        "archived_at":   time.strftime("%Y-%m-%d %H:%M"),
        "date_campagne": date_camp,
        "postes":        int(len(complet)) if complet is not None else int(state.get("ave_count", 0)),
        "retenus":       int(state.get("res_count", 0)) if complet is not None else 0,
        "vacants":       int(len(vac)) if vac is not None and complet is not None else None,
        "has_results":   complet is not None,
        "has_site":      (dest / "site" / "index.html").exists(),
        "additifs":      len(state.get("additifs_applied", [])),
    }
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def list_archives(data_dir: Path) -> list[dict]:
    out = []
    root = archives_root(data_dir)
    if root.is_dir():
        for m in root.glob("*/meta.json"):
            try:
                meta = read_json(m)
                meta["has_site"] = (m.parent / "site" / "index.html").exists()
                out.append(meta)
            except Exception:
                pass
    return sorted(out, key=lambda x: x.get("date_campagne", ""), reverse=True)


def archive_dir(data_dir: Path, slug: str) -> Path | None:
    """Chemin d'une archive existante (le slug doit correspondre à une archive listée)."""
    if slug not in {a["slug"] for a in list_archives(data_dir)}:
        return None
    return archives_root(data_dir) / slug


# ── Historique des postes non pourvus ─────────────────────────────────────────

def vacants_history(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Retourne (detail, recurrents) :
    - detail     : une ligne par poste non pourvu et par campagne archivée avec résultats
    - recurrents : un poste (même intitulé + service + commune) et le nombre de
                   campagnes où il est resté non pourvu, du plus récurrent au moins récurrent
    """
    frames = []
    archives = [a for a in list_archives(data_dir) if a.get("has_results")]
    for a in sorted(archives, key=lambda x: x.get("date_campagne", "")):
        v = _vacants(archives_root(data_dir) / a["slug"] / "processed")
        if v is None or v.empty:
            continue
        v = v.copy()
        v.insert(0, "Campagne", a["campaign"])
        v.insert(1, "_date", a.get("date_campagne", ""))
        frames.append(v)

    if not frames:
        empty = pd.DataFrame(columns=["Campagne"] + HIST_COLS)
        return empty, pd.DataFrame(columns=["Poste", "Service", "Commune", "Grand service",
                                            "Nb campagnes", "Campagnes", "Dernier N° AVE"])

    detail = pd.concat(frames, ignore_index=True)
    detail["Poste"] = detail["Libellé du poste"].map(_poste_label)
    detail["_key"] = (detail["Poste"].map(_ascii) + "|" + detail["Service"].map(_ascii)
                      + "|" + detail["Commune"].map(lambda c: _ascii(_commune(c))))

    rec = (detail.sort_values("_date")
           .groupby("_key")
           .agg(**{
               "Poste":          ("Poste", "last"),
               "Service":        ("Service", "last"),
               "Commune":        ("Commune", lambda s: _commune(s.iloc[-1])),
               "Grand service":  ("Grand service", "last"),
               "Nb campagnes":   ("Campagne", "nunique"),
               "Campagnes":      ("Campagne", lambda s: " · ".join(dict.fromkeys(s))),
               "Dernier N° AVE": ("N° AVE", "last"),
           })
           .sort_values(["Nb campagnes", "Grand service", "Poste"], ascending=[False, True, True])
           .reset_index(drop=True))

    detail = detail.sort_values(["_date", "Grand service", "N° AVE"], ascending=[False, True, True])
    return detail.drop(columns=["_key", "_date"]), rec


def history_excel(data_dir: Path, out: Path) -> Path:
    detail, rec = vacants_history(data_dir)
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        rec.to_excel(xw, sheet_name="Récurrence", index=False)
        detail.to_excel(xw, sheet_name="Détail par campagne", index=False)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
    return out
