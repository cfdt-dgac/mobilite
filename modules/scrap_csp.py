#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrap_csp.py
Scraping de choisirleservicepublic.gouv.fr pour DGAC et Météo-France.
Adapté de scrap_csp_rss.py pour intégration dans l'appli Flask.
"""

import re
import time
import threading
from typing import Optional
import requests
from bs4 import BeautifulSoup, Tag
import pandas as pd

BASE    = "https://choisirleservicepublic.gouv.fr"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"}

# État global du scraping (partagé avec le thread Flask)
_scrape_state = {
    "running":  False,
    "done":     False,
    "progress": 0,
    "total":    0,
    "current":  "",
    "error":    "",
}


def get_scrape_state() -> dict:
    return dict(_scrape_state)


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _get_soup(url: str, sleep: float = 0.4) -> BeautifulSoup:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            r.raise_for_status()
            time.sleep(sleep)
            return BeautifulSoup(r.text, "html.parser")
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    return BeautifulSoup("", "html.parser")


def _abs(href: str) -> str:
    if href.startswith("http"):
        return href
    return BASE + ("/" if not href.startswith("/") else "") + href


def _txt(el: Optional[Tag]) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _strip_label(value: str, base: str) -> str:
    v = value.strip().replace("\xa0", " ")
    return re.sub(rf"^\s*{re.escape(base)}\s*:\s*", "", v, flags=re.IGNORECASE).strip()


# ── Pagination ────────────────────────────────────────────────────────────────

def _next_page(soup: BeautifulSoup) -> Optional[str]:
    for selector in [
        lambda s: s.find("a", rel=lambda v: v and "next" in v),
        lambda s: s.find("a", attrs={"aria-label": lambda v: v and "Suivant" in v}),
        lambda s: s.find("a", string=lambda v: v and "Suivant" in v),
    ]:
        a = selector(soup)
        if a and a.get("href"):
            return _abs(a["href"])
    return None


# Organismes dont on ne garde que les postes en métropole
_METROPOLE_ONLY_ORGS = {"13781"}  # ENAC

def _is_france(localisation: str) -> bool:
    """
    Retourne True si la localisation est en France (métropole + outre-mer).
    Exclut uniquement l'étranger (pas de code département français reconnu).
    Codes reconnus : 01–95 (métropole), 2A/2B (Corse), 971–989 (DOM-TOM/COM).
    """
    # Corse
    if re.search(r'\b2[AB]\b', localisation, re.IGNORECASE):
        return True
    # Cherche un code département/territoire français
    for m in re.finditer(r'\b(\d{2,3})\b', localisation):
        n = int(m.group(1))
        if 1 <= n <= 95:      # Métropole
            return True
        if 971 <= n <= 989:   # DOM-TOM / COM
            return True
    # Aucun code français trouvé → étranger
    return False


def _list_offers(tokens: list[str]) -> list[tuple[str, str]]:
    """
    Retourne une liste de (url, organisme_token) pour chaque offre trouvée.
    """
    results = []
    seen = set()
    for tok in tokens:
        tok = tok.strip()
        page_url = tok if tok.startswith("http") else f"{BASE}/nos-offres/filtres/organisme/{tok}/"
        page_n   = 1
        while page_url:
            print(f"  [CSP] page {page_n}: {page_url}")
            soup = _get_soup(page_url)
            for a in soup.find_all("a", href=True):
                if "/offre-emploi/" in a["href"]:
                    url = _abs(a["href"])
                    if url not in seen:
                        seen.add(url)
                        results.append((url, tok))
            page_url = _next_page(soup)
            page_n  += 1
    return results


# ── Extraction d'une fiche ────────────────────────────────────────────────────

def _norm_spaces(s: str) -> str:
    return s.replace("\xa0", " ")


def _unique_lines(text: str) -> str:
    lines, out = [l.rstrip() for l in text.splitlines()], []
    for l in lines:
        if not l.strip():
            if out and out[-1] == "":
                continue
            out.append("")
        elif out and l == out[-1]:
            continue
        else:
            out.append(l)
    while out and out[0]  == "": out.pop(0)
    while out and out[-1] == "": out.pop()
    return "\n".join(out)


def _block_text(el: Optional[Tag]) -> str:
    if not el:
        return ""
    el = BeautifulSoup(str(el), "html.parser")
    for br in el.find_all("br"):
        br.replace_with("\n")
    for li in el.find_all("li"):
        t = li.get_text(" ", strip=True)
        li.clear(); li.append(f"- {t}\n")
    for p in el.find_all("p"):
        t = p.get_text(" ", strip=True)
        p.clear(); p.append(t + "\n\n")
    for hh in el.find_all(["h3", "h4"]):
        t = hh.get_text(" ", strip=True)
        if re.search(r"(profil|mission|contexte|description)", t, re.I):
            hh.decompose()
        else:
            hh.clear(); hh.append(t + "\n\n")
    out = _norm_spaces(el.get_text("", strip=True))
    out = re.sub(r"\n{3,}", "\n\n", out)
    return _unique_lines(out)


def _section(soup: BeautifulSoup, keys: list[str]) -> str:
    col = soup.select_one("div.col-left.rte")
    if not col:
        return ""
    target = next(
        (h for h in col.find_all("h2")
         if any(k.lower() in h.get_text(" ", strip=True).lower() for k in keys)),
        None
    )
    if not target:
        return ""
    parts = []
    for sib in target.next_siblings:
        if isinstance(sib, Tag) and sib.name == "h2":
            break
        if isinstance(sib, Tag):
            chunk = _block_text(sib)
            if chunk:
                parts.append(chunk)
    txt = "\n".join(p for p in parts if p.strip())
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    txt = re.sub(r"^(vos?\s+missions.*)$", "", txt, flags=re.I | re.M)
    return _unique_lines(txt).strip()


def _intro(soup: BeautifulSoup) -> str:
    col = soup.select_one("div.col-left.rte")
    if not col:
        return ""
    parts = []
    for child in col.children:
        if isinstance(child, Tag) and child.name == "h2":
            break
        if isinstance(child, Tag):
            parts.append(_block_text(child))
    txt = "\n".join(p for p in parts if p.strip())
    return re.sub(r"\n{3,}", "\n\n", txt).strip()


def _emails(soup: BeautifulSoup) -> str:
    found = set()
    for a in soup.select('a[href^="mailto:"]'):
        m = a["href"].replace("mailto:", "").split("?")[0].strip()
        if m:
            found.add(m)
    for m in re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
                        soup.get_text(" ", strip=True)):
        found.add(m)
    found = [e for e in sorted(found) if not e.lower().endswith("@exemple.com")]
    return "\n".join(found)


def _ref_from_url(url: str) -> str:
    m = re.search(r"(?:reference-)?(\d{4}-\d{6,7}|\d{5,7})", url)
    return m.group(1) if m else ""


def _normalize_employeur(raw: str) -> str:
    """Normalise les noms d'employeurs CSP vers des valeurs canoniques."""
    import unicodedata
    s = raw.strip()
    s_ascii = ''.join(
        c for c in unicodedata.normalize('NFD', s.lower())
        if unicodedata.category(c) != 'Mn'
    )
    if "(sg)" in s_ascii or "secretariat general" in s_ascii:
        return "SG"
    if "(dta)" in s_ascii or "transport aerien" in s_ascii:
        return "DTA"
    if "dgac" in s_ascii or "aviation civile" in s_ascii:
        return "DGAC"
    return s


def _cell_by_strong(soup: BeautifulSoup, label: str) -> str:
    strong = soup.find("strong", string=lambda s: s and s.strip() == label)
    if not strong:
        return ""
    sib = strong.find_next_sibling()
    if sib:
        return sib.get_text("\n", strip=True)
    parent = strong.parent
    if parent:
        parts = list(parent.stripped_strings)
        if len(parts) >= 2:
            return " ".join(parts[1:])
    return ""


def parse_offer(url: str) -> dict:
    soup = _get_soup(url)
    titre       = _txt(soup.select_one("h1"))
    numero_ave  = ""
    ref = soup.find("p", class_="number")
    if ref:
        numero_ave = _txt(ref).replace("\xa0", " ").strip()
    if not numero_ave:
        numero_ave = _ref_from_url(url)
    numero_ave = re.sub(r"^\s*Réf\.\s*", "", numero_ave, re.I).strip()
    numero_ave = _strip_label(numero_ave, "Référence")

    return {
        "titre":           titre,
        "url":             url,
        "numero_ave":      numero_ave,
        "employeur":       _normalize_employeur(_strip_label(_txt(soup.select_one("li.ic.ic--user")), "Employeur")),
        "localisation":    _strip_label(_txt(soup.select_one("li.ic.ic--pin")),     "Localisation"),
        "domaine":         _strip_label(_txt(soup.select_one("a.fr-tag")),          "Domaine"),
        "categorie":       _cell_by_strong(soup, "Catégorie"),
        "experience":      _cell_by_strong(soup, "Expérience souhaitée"),
        "teletravail":     _cell_by_strong(soup, "Télétravail possible"),
        "remuneration":    _cell_by_strong(soup, "Rémunération"),
        "type_contrat":    _cell_by_strong(soup, "Nature du contrat"),
        "description":     _intro(soup),
        "missions":        _section(soup, ["missions", "vos missions"]),
        "profil_recherche":_section(soup, ["profil", "profil recherché"]),
        "contacts":        _emails(soup),
    }


# ── Point d'entrée public ─────────────────────────────────────────────────────

def scrape_csp(organismes: str, out_xlsx: str) -> None:
    """
    Lance le scraping CSP en mode synchrone.
    organismes : "417,417-390,13781"
    out_xlsx   : chemin du fichier de sortie
    """
    tokens    = [t.strip() for t in organismes.split(",") if t.strip()]
    url_pairs = _list_offers(tokens)
    print(f"[CSP] {len(url_pairs)} offres trouvées. Extraction…")

    rows = []
    for i, (url, tok) in enumerate(url_pairs, 1):
        print(f"  [{i}/{len(url_pairs)}] {url}")
        try:
            row = parse_offer(url)
            # Filtre métropole pour les organismes concernés
            if tok in _METROPOLE_ONLY_ORGS and not _is_france(row.get("localisation", "")):
                print(f"    → Ignoré (outre-mer)")
                continue
            rows.append(row)
        except Exception as ex:
            print(f"    Erreur: {ex}")

    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    df.to_excel(out_xlsx, index=False)
    print(f"[CSP] Terminé → {out_xlsx}")


def scrape_csp_background(organismes: str, out_xlsx: str) -> None:
    """Lance le scraping dans un thread séparé (non bloquant)."""
    _scrape_state.update(running=True, done=False, progress=0,
                         total=0, current="Démarrage…", error="")

    def _run():
        try:
            tokens = [t.strip() for t in organismes.split(",") if t.strip()]
            _scrape_state["current"] = "Récupération de la liste des offres…"
            url_pairs = _list_offers(tokens)
            _scrape_state["total"] = len(url_pairs)
            rows = []
            for i, (url, tok) in enumerate(url_pairs, 1):
                _scrape_state.update(progress=i, current=url)
                try:
                    row = parse_offer(url)
                    # Filtre métropole pour les organismes concernés
                    if tok in _METROPOLE_ONLY_ORGS and not _is_france(row.get("localisation", "")):
                        continue
                    rows.append(row)
                except Exception as ex:
                    print(f"    Erreur {url}: {ex}")

            df = pd.DataFrame(rows) if rows else pd.DataFrame()
            df.to_excel(out_xlsx, index=False)
            _scrape_state.update(running=False, done=True,
                                 current=f"Terminé — {len(rows)} offres")
        except Exception as ex:
            _scrape_state.update(running=False, done=False,
                                 error=str(ex), current="Erreur")

    threading.Thread(target=_run, daemon=True).start()
