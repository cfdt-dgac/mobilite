#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_ave.py
Lit le PDF AVE de l'administration et retourne un DataFrame propre,
équivalent à la sortie de la macro VBA "ALL".
"""

import re
import pdfplumber
import pandas as pd


# Colonnes finales attendues par le reste du pipeline
OUTPUT_COLS = [
    "Grand service",
    "Service",
    "Commune",
    "Libellé du poste",
    "Corps et restriction",
    "Agent remplacé",
    "N° AVE",
    "Première CDM d'ouverture du poste",
    "Statut",
]


def _clean_cell(v) -> str:
    if v is None:
        return ""
    return str(v).replace("\n", " ").strip()


def _clean_libelle(libelle_long: str) -> str:
    """Supprime le suffixe *SERVICE/UO du libellé long."""
    return re.sub(r"\*[A-Z0-9/\-]+$", "", libelle_long).strip()


def _format_libelle(nbre: int, libelle_long: str) -> str:
    label = _clean_libelle(libelle_long)
    if nbre > 1:
        return f"{nbre} postes — {label}"
    return f"1 poste — {label}"


def _is_section_header(row) -> tuple[bool, str]:
    """
    Détecte une ligne de type 'Grand service : ACBACEA'.
    Vérifie toutes les cellules (la cellule peut être fusionnée ou décalée).
    Concatène aussi toutes les cellules non-vides pour les cas où le texte
    est réparti sur plusieurs colonnes.
    """
    if not row:
        return False, ""
    # Essai cellule par cellule
    for cell in row:
        if cell:
            v = _clean_cell(cell)
            m = re.match(r"Grand\s+service\s*:\s*(.+)", v, re.IGNORECASE)
            if m:
                return True, m.group(1).strip()
    # Essai en concaténant toutes les cellules (cas texte réparti)
    full = " ".join(_clean_cell(c) for c in row if c)
    m = re.match(r"Grand\s+service\s*:\s*(.+)", full, re.IGNORECASE)
    if m:
        return True, m.group(1).strip()
    return False, ""


def _is_col_header(row) -> bool:
    """Détecte la ligne d'en-tête de tableau."""
    if row and row[0]:
        v = _clean_cell(row[0])
        return v.startswith("N°") or v == "N° AVE"
    return False


def _is_empty(row) -> bool:
    return not row or all(v is None or str(v).strip() == "" for v in row)


def _get_gs_from_text(page) -> list[tuple[float, str]]:
    """
    Extrait les titres 'Grand service : XXX' depuis le texte libre
    de la page, avec leur position verticale (top).
    Retourne une liste triée [(top, grand_service), ...].

    Stratégie : regroupe les mots par ligne (top arrondi),
    reconstitue chaque ligne et cherche le pattern.
    """
    from collections import defaultdict
    lines = defaultdict(list)
    for w in (page.extract_words() or []):
        top_key = round(w["top"] / 2) * 2   # arrondi à 2px
        lines[top_key].append(w)

    results = []
    for top_key in sorted(lines.keys()):
        words_sorted = sorted(lines[top_key], key=lambda w: w["x0"])
        line_text = " ".join(w["text"] for w in words_sorted)
        m = re.search(r"Grand\s+service\s*:\s*(.+)", line_text, re.IGNORECASE)
        if m:
            gs_name = m.group(1).strip()
            results.append((float(top_key), gs_name))

    return sorted(results)


def _process_table_rows(table_data: list, current_gs: str) -> list[dict]:
    """Extrait les lignes de données d'un tableau pdfplumber."""
    rows = []
    for row in table_data:
        if _is_empty(row):
            continue
        if _is_col_header(row):
            continue

        cells = [_clean_cell(c) for c in row]
        while len(cells) < 12:
            cells.append("")

        n_ave = cells[0]
        if not re.search(r"\d{5,7}", n_ave):
            continue

        rows.append({
            "grand_service": current_gs,
            "n_ave":         re.search(r"\d{4,7}", n_ave).group(),
            "nbre_poste":    cells[1],
            "corps":         cells[2],
            "uo":            cells[3],
            "service":       cells[4],
            "commune":       cells[5],
            "dpt":           cells[6],
            "libelle_long":  cells[7],
            "type_poste":    cells[8],
            "agent_remplace":cells[9],
            "statut_admin":  cells[10],
            "ave_precedent": cells[11],
        })
    return rows


def extract_raw_rows(pdf_path: str) -> list[dict]:
    """Extrait toutes les lignes brutes du PDF avec leur Grand service."""
    rows = []
    current_gs = ""

    TS = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # ── Positions Y des titres "Grand service : XXX" ─────────────
            gs_positions = _get_gs_from_text(page)  # [(top_y, gs_name), ...]

            # ── Tableaux avec leur position Y ─────────────────────────────
            try:
                found_tables = page.find_tables(TS)
            except Exception:
                found_tables = page.find_tables()

            if found_tables:
                for ft in found_tables:
                    table_top = ft.bbox[1]   # coordonnée Y du haut du tableau

                    # GS le plus récent dont la position Y est AU-DESSUS du tableau
                    for gs_top, gs_name in reversed(gs_positions):
                        if gs_top <= table_top:
                            current_gs = gs_name
                            break

                    rows.extend(_process_table_rows(ft.extract(), current_gs))

            else:
                # Fallback sans position : on extrait les tables normalement
                tables = page.extract_tables(TS) or page.extract_tables()
                for table in tables:
                    rows.extend(_process_table_rows(table, current_gs))

            # Mettre à jour current_gs avec le dernier GS de la page
            # (pour que la page suivante commence au bon GS)
            if gs_positions:
                current_gs = gs_positions[-1][1]

    # Propagation du GS manquant en dernier recours (sécurité)
    last_gs = ""
    for r in rows:
        if r["grand_service"]:
            last_gs = r["grand_service"]
        else:
            r["grand_service"] = last_gs

    return rows


def _concat_corps(series: pd.Series) -> str:
    parts = sorted({s.strip() for s in series if s and s.strip()})
    return " ; ".join(parts)


def process_raw_to_final(raw_rows: list[dict]) -> pd.DataFrame:
    """
    Regroupe les lignes brutes par N° AVE (une ligne = un AVE)
    et calcule les colonnes finales (équivalent macro VBA 'ALL').
    """
    if not raw_rows:
        return pd.DataFrame(columns=OUTPUT_COLS)

    df = pd.DataFrame(raw_rows)
    df["nbre_poste"] = pd.to_numeric(df["nbre_poste"], errors="coerce").fillna(1).astype(int)

    agg = df.groupby("n_ave", sort=False).agg(
        grand_service  = ("grand_service",  "first"),
        service        = ("service",        "first"),
        commune        = ("commune",        "first"),
        nbre_poste     = ("nbre_poste",     "first"),
        libelle_long   = ("libelle_long",   "first"),
        corps          = ("corps",          _concat_corps),
        agent_remplace = ("agent_remplace", "first"),
        statut_admin   = ("statut_admin",   "first"),
        ave_precedent  = ("ave_precedent",  "first"),
    ).reset_index()

    agg["libelle_poste"] = agg.apply(
        lambda r: _format_libelle(int(r["nbre_poste"]), r["libelle_long"]), axis=1
    )

    result = pd.DataFrame({
        "Grand service":                    agg["grand_service"],
        "Service":                          agg["service"],
        "Commune":                          agg["commune"],
        "Libellé du poste":                 agg["libelle_poste"],
        "Corps et restriction":             agg["corps"],
        "Agent remplacé":                   agg["agent_remplace"],
        "N° AVE":                           agg["n_ave"],
        "Première CDM d'ouverture du poste":agg["ave_precedent"],
        "Statut":                           agg["statut_admin"],
    })

    return result


def extract_ave_pdf(pdf_path: str) -> pd.DataFrame:
    """Point d'entrée principal : PDF AVE → DataFrame propre."""
    raw = extract_raw_rows(pdf_path)
    df = process_raw_to_final(raw)
    return df


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python extract_ave.py <chemin_pdf>")
        sys.exit(1)
    df = extract_ave_pdf(sys.argv[1])
    print(f"{len(df)} postes extraits")
    print(df.head())
