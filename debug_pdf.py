#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
debug_pdf.py — Diagnostic extraction PDF AVE
Usage : python debug_pdf.py <chemin_vers_ave.pdf>
"""
import sys
import pdfplumber

pdf_path = sys.argv[1] if len(sys.argv) > 1 else "data/uploads/ave.pdf"

print(f"Analyse de : {pdf_path}\n")

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages[:5], 1):  # 5 premières pages
        print(f"\n{'='*60}")
        print(f" PAGE {page_num}")
        print(f"{'='*60}")

        # ── Texte brut ──
        text = page.extract_text() or ""
        print("\n--- TEXTE BRUT (50 premières lignes) ---")
        for i, line in enumerate(text.splitlines()[:50]):
            print(f"  [{i:02d}] {repr(line)}")

        # ── Tables ──
        tables = page.extract_tables(
            table_settings={"vertical_strategy": "lines",
                             "horizontal_strategy": "lines"}
        )
        if not tables:
            tables = page.extract_tables()

        print(f"\n--- TABLES ({len(tables)} trouvées) ---")
        for t_idx, table in enumerate(tables):
            print(f"\n  Table {t_idx} ({len(table)} lignes) :")
            for r_idx, row in enumerate(table[:10]):  # 10 premières lignes
                non_empty = [str(c)[:40] if c else '' for c in row]
                print(f"    [{r_idx:02d}] {non_empty}")
