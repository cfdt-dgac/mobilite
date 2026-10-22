#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
campaign_info.py
Informations pratiques de la campagne (dates, contacts, notes de gestion),
modifiables depuis l'appli (page « Infos campagne ») et stockées dans
data/campaign_info.json — donc sauvegardées avec le dossier data/ de la campagne.
"""

import json
import re
from pathlib import Path

# Valeurs par défaut = celles de la 2ème campagne FIDELO 2026
DEFAULT_INFO = {
    "statut": "ouverte",   # "ouverte" ou "close"
    "date_limite": "lundi 31 août 2026",
    "date_avis": "lundi 7 septembre 2026",
    "date_resultats": "semaine 38 (du 14 au 18 septembre 2026)",
    "message": "",
    # Une ligne par contact : Corps | Nom | email
    "contacts": "\n".join([
        "IPEF et Administrateurs de l'État | Béatrice COQUET | beatrice.coquet@aviation-civile.gouv.fr",
        "ITPE, TSDD et ISIC | Anna POLONSKAYA | anna.polonskaya@aviation-civile.gouv.fr",
        "ITPE, TSDD et ISIC | Olivier GOURDON | olivier.gourdon@aviation-civile.gouv.fr",
        "IEEAC | Nadia BOUAD | nadia.bouad@aviation-civile.gouv.fr",
        "Attachés et PNT | Béatrice COQUET | beatrice.coquet@aviation-civile.gouv.fr",
        "Assistants | Jean-Louis LEPREUX | jean-louis.lepreux@aviation-civile.gouv.fr",
        "Adjoints | Maryse LE-STER | maryse.le-ster@aviation-civile.gouv.fr",
        "Ouvriers d'État & OPA | Anne-Marie DOS SANTOS | anne-marie.dos-santos@aviation-civile.gouv.fr",
        "ICNA | Philippe HERRERO | sdrh-mobilite-icna-ld@aviation-civile.gouv.fr",
        "IESSA | Jean-Claude LAMOUREUX | sdrh-mobilite-iessa-ld@aviation-civile.gouv.fr",
        "TSEEAC | Cécile CORREA-DOISY | sdrh-mobilite-tseeac-ld@aviation-civile.gouv.fr",
    ]),
    # Une ligne par document : Libellé | URL
    "notes": "\n".join([
        "Lignes directrices de gestion mobilité DGAC | https://www.cfdtdgac.fr/upload/media-library/2026/09/18/7eca2287-6bd8-4f81-9597-9b9b7122d349.pdf",
        "Note de gestion ICNA (2026) | https://www.cfdtdgac.fr/upload/media-library/2026/09/18/f95165a6-80e8-4abf-aa43-274a48dbd921.pdf",
        "Note de gestion IESSA (2021) | https://www.cfdtdgac.fr/upload/media-library/2026/09/18/7e8a4b79-4a83-4309-9be9-433003bd2ab9.pdf",
        "Note de gestion TSEEAC (2021) | https://www.cfdtdgac.fr/upload/media-library/2026/09/18/67974b04-7c4f-4bdf-84b9-c47c2425cc28.pdf",
        "Note de gestion OE (2020) | https://www.cfdtdgac.fr/upload/media-library/2026/09/18/f897dd61-cf56-46c1-8e38-81950424f15f.pdf",
    ]),
}

FIELDS = list(DEFAULT_INFO.keys())

_EMAIL_RE = re.compile(r"^[\w.+\-]+@[\w\-]+(\.[\w\-]+)+$")


def load_info(path: Path) -> dict:
    info = dict(DEFAULT_INFO)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            info.update({k: str(v) for k, v in data.items() if k in DEFAULT_INFO})
        except Exception:
            pass
    return info


def save_info(path: Path, form: dict) -> dict:
    info = {k: str(form.get(k, DEFAULT_INFO[k]) or "").strip() for k in FIELDS}
    if info["statut"] not in ("ouverte", "close"):
        info["statut"] = "ouverte"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def parse_contacts(text: str) -> tuple[list[tuple[str, list[tuple[str, str]]]], list[str]]:
    """'Corps | Nom | email' → [(corps, [(nom, email), ...]), ...] (ordre conservé,
    même corps regroupé). Retourne aussi la liste des lignes invalides."""
    groups: dict[str, list] = {}
    errors = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3 or not _EMAIL_RE.match(parts[2]):
            errors.append(line)
            continue
        groups.setdefault(parts[0], []).append((parts[1], parts[2]))
    return list(groups.items()), errors


def parse_notes(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    """'Libellé | URL' → [(libellé, url), ...] + lignes invalides."""
    out, errors = [], []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|", 1)]
        if len(parts) != 2 or not re.match(r"^https?://", parts[1], re.I):
            errors.append(line)
            continue
        out.append((parts[0], parts[1]))
    return out, errors
