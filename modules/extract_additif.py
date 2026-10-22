#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_additif.py
Lit un PDF additif/modificatif et retourne :
  - un DataFrame des changements (par N° AVE)
  - la date d'édition du document
"""

import re
import pdfplumber
import pandas as pd
from .extract_ave import _clean_cell, _clean_libelle, _format_libelle


def _extract_date(pdf_path: str) -> str:
    """Extrait la date 'Edité le JJ/MM/AAAA' du PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            m = re.search(r"[Ee]dit[eé]\s+le\s+(\d{2}/\d{2}/\d{4})", text)
            if m:
                return m.group(1)
    return ""


def _get_gs_from_text(page) -> list[tuple[float, str]]:
    """Extrait les titres 'Grand service : XXX' depuis le texte de la page."""
    results = []
    text = page.extract_text() or ""
    for line in text.splitlines():
        m = re.search(r"Grand\s+service\s*:\s*(.+)", line, re.IGNORECASE)
        if m:
            gs_name = m.group(1).strip()
            for w in page.extract_words():
                if "Grand" in w["text"] and w["top"] not in [r[0] for r in results]:
                    results.append((w["top"], gs_name))
                    break
    return sorted(results)


def _is_col_header(row) -> bool:
    if row and row[0]:
        v = _clean_cell(row[0])
        return v.startswith("N°") or v == "N° AVE"
    return False


def _is_empty(row) -> bool:
    return not row or all(v is None or str(v).strip() == "" for v in row)


def extract_additif_pdf(pdf_path: str) -> tuple[pd.DataFrame, str]:
    """
    Point d'entrée : PDF additif/modificatif → (DataFrame, date_str).

    Colonnes du DataFrame retourné :
      N° AVE, Grand service, Service, Commune, Libellé du poste,
      Corps et restriction, Agent remplacé, Statut_raw, Type_additif
    """
    date_str = _extract_date(pdf_path)
    raw_rows = []
    current_gs = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            gs_positions = _get_gs_from_text(page)

            tables = page.extract_tables(
                table_settings={"vertical_strategy": "lines",
                                 "horizontal_strategy": "lines"}
            )
            if not tables:
                tables = page.extract_tables()

            for table in tables:
                for row in table:
                    if _is_empty(row) or _is_col_header(row):
                        continue

                    cells = [_clean_cell(c) for c in row]
                    while len(cells) < 13:
                        cells.append("")

                    n_ave = cells[0]
                    if not re.search(r"\d{5,7}", n_ave):
                        continue

                    m = re.search(r"\d{4,7}", n_ave)
                    if not m:
                        continue

                    raw_rows.append({
                        "grand_service":  current_gs,
                        "n_ave":          m.group(),
                        "nbre_poste":     cells[1],
                        "corps":          cells[2],
                        "uo":             cells[3],
                        "service":        cells[4],
                        "commune":        cells[5],
                        "libelle_long":   cells[7],
                        "type_poste":     cells[8],
                        "agent_remplace": cells[9],
                        "statut_raw":     cells[10].strip().upper(),
                        "type_additif":   cells[12].strip(),  # "Additif" ou "Modificatif"
                    })

            if gs_positions:
                current_gs = gs_positions[-1][1]
                for r in raw_rows:
                    if not r["grand_service"]:
                        r["grand_service"] = gs_positions[0][1]

    # Propagation GS
    last_gs = ""
    for r in raw_rows:
        if r["grand_service"]:
            last_gs = r["grand_service"]
        else:
            r["grand_service"] = last_gs

    if not raw_rows:
        return pd.DataFrame(), date_str

    df = pd.DataFrame(raw_rows)
    df["nbre_poste"] = pd.to_numeric(df["nbre_poste"], errors="coerce").fillna(1).astype(int)

    def _concat_corps(series):
        parts = sorted({s.strip() for s in series if s and s.strip()})
        return " ; ".join(parts)

    def _first_statut(series):
        """Priorité à 'F' si au moins une ligne est fermée."""
        vals = [v.strip().upper() for v in series if v.strip()]
        if "F" in vals:
            return "F"
        return vals[0] if vals else "O"

    def _first_type(series):
        """Priorité à 'Modificatif' si présent."""
        vals = [v.strip() for v in series if v.strip()]
        if any("odificatif" in v for v in vals):
            return "Modificatif"
        return vals[0] if vals else "Additif"

    agg = df.groupby("n_ave", sort=False).agg(
        grand_service  = ("grand_service",  "first"),
        service        = ("service",        "first"),
        commune        = ("commune",        "first"),
        nbre_poste     = ("nbre_poste",     "first"),
        libelle_long   = ("libelle_long",   "first"),
        corps          = ("corps",          _concat_corps),
        agent_remplace = ("agent_remplace", "first"),
        statut_raw     = ("statut_raw",     _first_statut),
        type_additif   = ("type_additif",   _first_type),
    ).reset_index()

    agg["libelle_poste"] = agg.apply(
        lambda r: _format_libelle(int(r["nbre_poste"]), r["libelle_long"]), axis=1
    )

    result = pd.DataFrame({
        "N° AVE":              agg["n_ave"],
        "Grand service":       agg["grand_service"],
        "Service":             agg["service"],
        "Commune":             agg["commune"],
        "Libellé du poste":    agg["libelle_poste"],
        "Corps et restriction":agg["corps"],
        "Agent remplacé":      agg["agent_remplace"],
        "Statut_raw":          agg["statut_raw"],
        "Type_additif":        agg["type_additif"],
    })

    return result, date_str
