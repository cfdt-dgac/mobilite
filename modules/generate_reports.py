#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_reports.py
Génère les rapports imprimables (HTML → PDF via navigateur, ou téléchargement HTML).
3 rapports :
  - Par Grand service : liste des agents retenus + postes vacants
  - Par Corps        : idem filtré par corps
  - Postes vacants   : uniquement les postes non pourvus
"""

import re
from pathlib import Path
import pandas as pd


_CSS = """
<style>
@page { size: A4 landscape; margin: 12mm; }
* { box-sizing: border-box; }
body { font-family: Arial, 'Segoe UI', sans-serif; font-size: 11px; color: #222; margin: 0; }
h1 { font-size: 16px; color: #E7591C; margin: 0 0 4px; }
h2 { font-size: 13px; color: #E7591C; margin: 16px 0 4px; border-bottom: 1px solid #E7591C; padding-bottom: 2px; }
.meta { font-size: 11px; color: #666; margin-bottom: 14px; }
table { border-collapse: collapse; width: 100%; margin-bottom: 10px; }
th { background: #E7591C; color: #fff; padding: 5px 6px; text-align: left; font-size: 10px; }
td { border: 1px solid #ddd; padding: 4px 6px; vertical-align: top; }
tr:nth-child(even) td { background: #fafafa; }
.vacant td { color: #999; font-style: italic; }
.retenu td:nth-child(6) { color: #E7591C; font-weight: bold; }
.badge { background: rgba(231,89,28,.12); border: 1px solid rgba(231,89,28,.3);
  color: #E7591C; border-radius: 999px; padding: 1px 7px; font-size: 10px; font-weight: bold; }
.stats { display: flex; gap: 24px; margin-bottom: 14px; }
.stat-box { background: #fafafa; border: 1px solid #ddd; border-radius: 8px;
  padding: 8px 14px; text-align: center; }
.stat-box .val { font-size: 22px; font-weight: 800; color: #E7591C; }
.stat-box .lbl { font-size: 10px; color: #666; }
@media print { .no-print { display: none !important; } }
</style>
"""

_PRINT_BTN = """
<div class="no-print" style="text-align:right;margin-bottom:12px">
  <button onclick="window.print()"
    style="background:#E7591C;color:#fff;border:none;padding:8px 18px;
           border-radius:999px;cursor:pointer;font-weight:700">
    🖨 Imprimer / Enregistrer en PDF
  </button>
</div>
"""


def _header(title: str, campaign: str, nb_retenus: int, nb_vacants: int) -> str:
    return f"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8">
<title>{title}</title>
{_CSS}
</head><body>
{_PRINT_BTN}
<h1>{title}</h1>
<p class="meta">Campagne : <strong>{campaign}</strong></p>
<div class="stats">
  <div class="stat-box"><div class="val">{nb_retenus + nb_vacants}</div><div class="lbl">Postes totaux</div></div>
  <div class="stat-box"><div class="val">{nb_retenus}</div><div class="lbl">Agents retenus</div></div>
  <div class="stat-box"><div class="val">{nb_vacants}</div><div class="lbl">Postes vacants</div></div>
</div>
"""


def _table_rows(df: pd.DataFrame) -> str:
    rows = []
    for _, r in df.iterrows():
        agent = str(r.get("Agent retenu", "") or "")
        cls   = "retenu" if agent else "vacant"
        ave   = str(r.get("N° AVE", "") or "")
        rows.append(
            f'<tr class="{cls}">'
            f'<td>{r.get("Grand service","")}</td>'
            f'<td>{r.get("Service","")}</td>'
            f'<td>{r.get("Commune","")}</td>'
            f'<td>{r.get("Libellé du poste","")}</td>'
            f'<td>{r.get("Corps et restriction","")}</td>'
            f'<td>{agent or "— vacant —"}</td>'
            f'<td>{r.get("Corps retenu","")}</td>'
            f'<td><span class="badge">{ave}</span></td>'
            f'</tr>'
        )
    return "\n".join(rows)


# ── Rapport par Grand service ─────────────────────────────────────────────────

def report_par_grand_service(df: pd.DataFrame, campaign: str, outdir: str) -> str:
    """Génère un HTML imprimable organisé par Grand service."""
    out  = Path(outdir)
    path = out / f"rapport_grand_service_{campaign.replace(' ','_')}.html"

    nb_ret = (df["Agent retenu"] != "").sum() if "Agent retenu" in df.columns else 0
    nb_vac = (df["Agent retenu"] == "").sum() if "Agent retenu" in df.columns else len(df)

    html = _header(f"Résultats CDM — par Grand service", campaign, int(nb_ret), int(nb_vac))
    html += """<table>
<thead><tr>
  <th>Grand service</th><th>Service</th><th>Commune</th>
  <th>Libellé du poste</th><th>Corps</th>
  <th>Agent retenu</th><th>Corps retenu</th><th>N° AVE</th>
</tr></thead><tbody>
"""
    df_sorted = df.sort_values(["Grand service", "Service", "Commune"])
    last_gs   = None
    rows      = []
    for _, r in df_sorted.iterrows():
        gs = str(r.get("Grand service", ""))
        if gs != last_gs:
            rows.append(f'<tr><td colspan="8" style="background:#fff3ee;font-weight:700;'
                        f'color:#E7591C;padding:6px">{gs}</td></tr>')
            last_gs = gs
        agent = str(r.get("Agent retenu", "") or "")
        cls   = "retenu" if agent else "vacant"
        rows.append(
            f'<tr class="{cls}">'
            f'<td></td>'
            f'<td>{r.get("Service","")}</td>'
            f'<td>{r.get("Commune","")}</td>'
            f'<td>{r.get("Libellé du poste","")}</td>'
            f'<td>{r.get("Corps et restriction","")}</td>'
            f'<td>{agent or "— vacant —"}</td>'
            f'<td>{r.get("Corps retenu","")}</td>'
            f'<td><span class="badge">{r.get("N° AVE","")}</span></td>'
            f'</tr>'
        )

    html += "\n".join(rows) + "</tbody></table></body></html>"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)


# ── Rapport par Corps ─────────────────────────────────────────────────────────

def report_par_corps(df: pd.DataFrame, campaign: str, outdir: str) -> dict[str, str]:
    """
    Génère un HTML imprimable par corps.
    Retourne un dict {corps: chemin_fichier}.
    """
    out   = Path(outdir)
    files = {}

    # Éclater les corps concaténés
    exploded = df.copy()
    exploded["_corps_unit"] = exploded["Corps et restriction"].str.split(r"\s*;\s*")
    exploded = exploded.explode("_corps_unit")
    exploded["_corps_unit"] = exploded["_corps_unit"].str.strip()

    for corps, grp in exploded.groupby("_corps_unit"):
        if not corps:
            continue
        nb_ret = int((grp["Agent retenu"] != "").sum()) if "Agent retenu" in grp.columns else 0
        nb_vac = int((grp["Agent retenu"] == "").sum()) if "Agent retenu" in grp.columns else len(grp)

        html  = _header(f"Résultats CDM — Corps {corps}", campaign, nb_ret, nb_vac)
        html += f"<h2>Corps : {corps}</h2>"
        html += """<table>
<thead><tr>
  <th>Grand service</th><th>Service</th><th>Commune</th>
  <th>Libellé du poste</th><th>Corps</th>
  <th>Agent retenu</th><th>Corps retenu</th><th>N° AVE</th>
</tr></thead><tbody>
"""
        html += _table_rows(grp.sort_values(["Grand service", "Commune"]))
        html += "</tbody></table></body></html>"

        safe  = re.sub(r"[^A-Za-z0-9_]", "_", corps)
        fname = out / f"rapport_corps_{safe}_{campaign.replace(' ','_')}.html"
        fname.parent.mkdir(parents=True, exist_ok=True)
        fname.write_text(html, encoding="utf-8")
        files[corps] = str(fname)

    return files


# ── Rapport postes vacants ────────────────────────────────────────────────────

def report_vacants(df: pd.DataFrame, campaign: str, outdir: str) -> str:
    """Génère un HTML des postes restés vacants."""
    out  = Path(outdir)
    path = out / f"rapport_vacants_{campaign.replace(' ','_')}.html"

    vacants = df[df.get("Agent retenu", pd.Series([""])) == ""] if "Agent retenu" in df.columns else df
    n = len(vacants)

    html  = _header(f"Postes vacants — {campaign}", campaign, 0, n)
    html += f"<p style='color:#E7591C;font-weight:700'>{n} poste(s) vacant(s)</p>"
    html += """<table>
<thead><tr>
  <th>Grand service</th><th>Service</th><th>Commune</th>
  <th>Libellé du poste</th><th>Corps</th><th>N° AVE</th>
</tr></thead><tbody>
"""
    for _, r in vacants.sort_values(["Grand service", "Commune"]).iterrows():
        html += (
            f'<tr>'
            f'<td>{r.get("Grand service","")}</td>'
            f'<td>{r.get("Service","")}</td>'
            f'<td>{r.get("Commune","")}</td>'
            f'<td>{r.get("Libellé du poste","")}</td>'
            f'<td>{r.get("Corps et restriction","")}</td>'
            f'<td><span class="badge">{r.get("N° AVE","")}</span></td>'
            f'</tr>\n'
        )
    html += "</tbody></table></body></html>"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path)


