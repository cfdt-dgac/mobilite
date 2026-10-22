#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_data.py
Jointure AVE ↔ Résultats CDM, calcul des postes vacants.
"""

import re
import pandas as pd


def _norm_ave(v) -> str:
    """Normalise un N° AVE : extrait les chiffres, retire les zéros de tête."""
    s = re.sub(r"[^\d]", "", str(v or ""))
    return s.lstrip("0") or s


def merge_ave_resultats(
    df_ave: pd.DataFrame,
    df_resultats: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Joint le tableau AVE avec les résultats CDM.

    Retourne (df_complet, df_retenus, df_vacants) :
    - df_complet  : toutes les lignes AVE avec colonne 'Agent retenu' et 'Corps retenu'
    - df_retenus  : postes pourvus (Agent retenu renseigné)
    - df_vacants  : postes restés vacants (AVE sans agent retenu dans les résultats)
    """
    ave = df_ave.copy()
    res = df_resultats.copy()

    ave["_key"] = ave["N° AVE"].map(_norm_ave)
    res["_key"] = res["N° AVE"].map(_norm_ave)

    # Rang dans le groupe : permet d'apparier le Nième agent avec le Nième poste
    # quand un même N° AVE couvre plusieurs postes avec plusieurs candidats retenus
    ave["_rank"] = ave.groupby("_key").cumcount()
    res["_rank"] = res.groupby("_key").cumcount()

    # Si un AVE a plus d'agents retenus que de lignes dans le tableau AVE,
    # on duplique la ligne AVE pour chaque agent supplémentaire
    ave_counts = ave.groupby("_key").size()
    res_counts = res.groupby("_key").size()
    extra_rows = []
    for key in res_counts.index:
        n_res = int(res_counts[key])
        n_ave = int(ave_counts.get(key, 0))
        if n_res > n_ave > 0:
            last_row = ave[ave["_key"] == key].iloc[-1].copy()
            for extra_rank in range(n_ave, n_res):
                r = last_row.copy()
                r["_rank"] = extra_rank
                extra_rows.append(r)
    if extra_rows:
        ave = pd.concat([ave, pd.DataFrame(extra_rows)], ignore_index=True)

    # Garder seulement les colonnes utiles des résultats
    # On récupère aussi le Grand service des résultats pour corriger les erreurs du tableau AVE
    res_slim = res[["_key", "_rank", "Agent retenu", "Corps retenu", "Ville", "Grand service"]].copy()
    res_slim = res_slim.rename(columns={"Grand service": "_gs_res"})

    merged = ave.merge(res_slim, on=["_key", "_rank"], how="left")
    merged = merged.drop(columns=["_key", "_rank"])

    # Remplir les NaN
    merged["Agent retenu"] = merged["Agent retenu"].fillna("")
    merged["Corps retenu"] = merged["Corps retenu"].fillna("")
    merged["Ville"] = merged.get("Ville", "").fillna("")

    # Quand un agent est retenu, le Grand service des résultats prime sur celui du tableau AVE
    # (corrige les erreurs de classification dans le PDF AVE)
    if "_gs_res" in merged.columns:
        mask_retenu = (merged["Agent retenu"] != "") & (merged["_gs_res"].notna()) & (merged["_gs_res"] != "")
        merged.loc[mask_retenu, "Grand service"] = merged.loc[mask_retenu, "_gs_res"]
        merged = merged.drop(columns=["_gs_res"])

    df_retenus = merged[merged["Agent retenu"] != ""].copy()
    df_vacants = merged[merged["Agent retenu"] == ""].copy()

    return merged, df_retenus, df_vacants


def apply_additif(
    df_ave: pd.DataFrame,
    df_additif: pd.DataFrame,
    date_str: str,
) -> pd.DataFrame:
    """
    Applique un tableau additif/modificatif sur le DataFrame AVE principal.

    Règles :
    - Statut "F"           → colonne Statut = "Fermé le {date}", colonne _ferme = True
    - Statut "O" + Modif.  → colonne Statut = "Modifié le {date}", mise à jour des champs
    - Statut "O" + Additif → ajout de la ligne si N° AVE absent du tableau principal
    - "O" restants         → "Ouvert"
    """
    ave = df_ave.copy()
    ave["_key"] = ave["N° AVE"].map(_norm_ave)

    # Colonne marquage fermeture (False par défaut)
    if "_ferme" not in ave.columns:
        ave["_ferme"] = False

    # Normaliser Statut "O" → "Ouvert" sur le tableau existant
    if "Statut" in ave.columns:
        ave["Statut"] = ave["Statut"].apply(
            lambda s: "Ouvert" if str(s).strip().upper() == "O" else s
        )

    new_rows = []

    for _, patch in df_additif.iterrows():
        key = _norm_ave(patch["N° AVE"])
        statut = str(patch.get("Statut_raw", "")).strip().upper()
        t_type = str(patch.get("Type_additif", "")).strip()

        mask = ave["_key"] == key

        if statut == "F":
            # Fermeture — barrer la ligne et mettre à jour le statut
            ave.loc[mask, "Statut"] = f"Fermé le {date_str}"
            ave.loc[mask, "_ferme"] = True

        elif statut == "O" and "odificatif" in t_type:
            # Modificatif ouvert — mise à jour des champs modifiés
            if mask.any():
                ave.loc[mask, "Statut"] = f"Modifié le {date_str}"
                # Mettre à jour les champs qui ont changé
                for col, patch_col in [
                    ("Service",             "Service"),
                    ("Commune",             "Commune"),
                    ("Libellé du poste",    "Libellé du poste"),
                    ("Corps et restriction","Corps et restriction"),
                    ("Agent remplacé",      "Agent remplacé"),
                ]:
                    if patch_col in patch.index and patch[patch_col]:
                        ave.loc[mask, col] = patch[patch_col]
            else:
                # N° AVE inconnu → ajouter comme nouvel additif
                new_rows.append(_patch_to_row(patch, f"Modifié le {date_str}"))

        elif statut == "O" and "dditif" in t_type:
            # Additif pur — ajouter seulement si N° AVE absent
            if not mask.any():
                new_rows.append(_patch_to_row(patch, "Ouvert"))

    # Ajouter les nouvelles lignes
    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df_new["_key"]   = df_new["N° AVE"].map(_norm_ave)
        df_new["_ferme"] = False
        ave = pd.concat([ave, df_new], ignore_index=True)

    # Normaliser tous les "O" résiduels → "Ouvert"
    ave["Statut"] = ave["Statut"].apply(
        lambda s: "Ouvert" if str(s).strip().upper() == "O" else s
    )

    return ave.drop(columns=["_key"])


def normalize_statut(df_ave: pd.DataFrame) -> pd.DataFrame:
    """Remplace les 'O' par 'Ouvert' dans la colonne Statut."""
    df = df_ave.copy()
    if "Statut" in df.columns:
        df["Statut"] = df["Statut"].apply(
            lambda s: "Ouvert" if str(s).strip().upper() == "O" else s
        )
    return df


def _patch_to_row(patch: pd.Series, statut: str) -> dict:
    """Convertit une ligne additif en ligne AVE standard."""
    from .extract_ave import OUTPUT_COLS
    row = {c: "" for c in OUTPUT_COLS}
    row.update({
        "N° AVE":               str(patch.get("N° AVE", "")),
        "Grand service":        str(patch.get("Grand service", "")),
        "Service":              str(patch.get("Service", "")),
        "Commune":              str(patch.get("Commune", "")),
        "Libellé du poste":     str(patch.get("Libellé du poste", "")),
        "Corps et restriction": str(patch.get("Corps et restriction", "")),
        "Agent remplacé":       str(patch.get("Agent remplacé", "")),
        "Statut":               statut,
    })
    return row


def stats_par_corps(df: pd.DataFrame) -> pd.DataFrame:
    """Nombre de postes retenus / vacants par corps (Corps et restriction)."""
    if df.empty:
        return pd.DataFrame()

    # Éclater les corps concaténés ("AC84 ; ADAAC") en lignes individuelles
    exploded = df.copy()
    exploded["corps_unit"] = exploded["Corps et restriction"].str.split(r"\s*;\s*")
    exploded = exploded.explode("corps_unit")
    exploded["corps_unit"] = exploded["corps_unit"].str.strip()

    total   = exploded.groupby("corps_unit").size().rename("Total")
    retenus = exploded[exploded["Agent retenu"] != ""].groupby("corps_unit").size().rename("Retenus")
    vacants = exploded[exploded["Agent retenu"] == ""].groupby("corps_unit").size().rename("Vacants")

    stats = pd.concat([total, retenus, vacants], axis=1).fillna(0).astype(int)
    stats = stats.reset_index().rename(columns={"corps_unit": "Corps"})
    return stats.sort_values("Corps")


def stats_par_grand_service(df: pd.DataFrame) -> pd.DataFrame:
    """Nombre de postes retenus / vacants par Grand service."""
    if df.empty:
        return pd.DataFrame()

    total   = df.groupby("Grand service").size().rename("Total")
    retenus = df[df["Agent retenu"] != ""].groupby("Grand service").size().rename("Retenus")
    vacants = df[df["Agent retenu"] == ""].groupby("Grand service").size().rename("Vacants")

    stats = pd.concat([total, retenus, vacants], axis=1).fillna(0).astype(int)
    return stats.reset_index().sort_values("Grand service")
