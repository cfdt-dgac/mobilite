#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_resultats.py
Lit le PDF de résultats CDM de l'administration.
Colonnes attendues : Grand service, AVE, Ville (Département),
                     Unité Organisationnelle, Poste, Nom Prénom, Corps
"""

import re
import pdfplumber
import pandas as pd


OUTPUT_COLS = [
    "Grand service",
    "N° AVE",
    "Ville",
    "Unité Organisationnelle",
    "Poste",
    "Agent retenu",
    "Corps retenu",
]

# En-têtes connus dans le PDF de résultats
_KNOWN_HEADERS = {"grand service", "ave", "ville", "unité", "poste", "nom", "corps"}


def _clean(v) -> str:
    if v is None:
        return ""
    return str(v).replace("\n", " ").strip()


def _is_header_row(row) -> bool:
    if not row:
        return False
    first = _clean(row[0]).lower()
    return first in ("grand service", "grand") or first.startswith("grand serv")


def _is_empty(row) -> bool:
    return not row or all(v is None or str(v).strip() == "" for v in row)


def _looks_like_ave(v: str) -> bool:
    return bool(re.match(r"^\d{5,7}$", v.strip()))


def extract_resultats_pdf(pdf_path: str) -> pd.DataFrame:
    """
    Extrait les agents retenus depuis le PDF de résultats CDM.
    Retourne un DataFrame avec les colonnes OUTPUT_COLS.
    """
    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if _is_empty(row) or _is_header_row(row):
                        continue

                    cells = [_clean(c) for c in row]
                    while len(cells) < 7:
                        cells.append("")

                    # La colonne AVE (index 1) doit ressembler à un numéro
                    ave = cells[1].strip()
                    if not _looks_like_ave(ave):
                        # Cas particulier : certaines pages ont 'Grand service'
                        # fusionné sur 2 colonnes — on tente index 0 comme AVE
                        if _looks_like_ave(cells[0]):
                            # décalage : pas de grand_service sur cette ligne
                            cells = [""] + cells
                            ave = cells[1]
                        else:
                            continue

                    rows.append({
                        "Grand service":          cells[0],
                        "N° AVE":                 ave,
                        "Ville":                  cells[2],
                        "Unité Organisationnelle":cells[3],
                        "Poste":                  cells[4],
                        "Agent retenu":           cells[5],
                        "Corps retenu":           cells[6],
                    })

    if not rows:
        return pd.DataFrame(columns=OUTPUT_COLS)

    df = pd.DataFrame(rows)

    # Propagation du Grand service quand la cellule est vide
    # (cas de tableaux multi-pages sans répétition du GS)
    df["Grand service"] = df["Grand service"].replace("", None).ffill().fillna("")

    return df[OUTPUT_COLS].reset_index(drop=True)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python extract_resultats.py <chemin_pdf>")
        sys.exit(1)
    df = extract_resultats_pdf(sys.argv[1])
    print(f"{len(df)} agents retenus extraits")
    print(df.head())
