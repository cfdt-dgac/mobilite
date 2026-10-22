#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_sirh.py
Importation et normalisation des données issues du scraper SIRH v4
(fichier offres_sirh.json généré par scraper_sirh_console.js v4).

Format v4 : chaque fiche est un dict plat avec clés normalisées (accents
supprimés, caractères non-alphanumériques → '_').

Clés typiques produites par v4 :
  n_de_l_ave, libelle_de_l_ave, grand_service, poste, unite_organisationnelle,
  emploi, filiere, metier, type_de_poste, personne_remplacee,
  nombre_de_poste, vacance_immediate_eventuelle,
  corps_liste, restrictions_grades,
  definition, taches, commentaires, profil_qualification,
  responsable (dict : nom, numero_de_telephone, adresse_electronique),
  autre_contact (dict : …)
"""

import json
import re
from pathlib import Path
import pandas as pd


# ── Normalisation clé (même logique que normKey() en JS) ─────────────────────
_ACCENTS = str.maketrans({
    'é':'e','è':'e','ë':'e','ê':'e',
    'à':'a','â':'a','ä':'a',
    'ù':'u','û':'u','ü':'u',
    'ô':'o','ö':'o',
    'î':'i','ï':'i',
    'ç':'c',
})

def _norm_key(s: str) -> str:
    s = s.lower().translate(_ACCENTS)
    s = re.sub(r'[^a-z0-9]+', '_', s)
    return s.strip('_')[:55]


def _norm_ave(v) -> str:
    """Normalise un N° AVE : extrait les chiffres, retire les zéros de tête."""
    s = re.sub(r'[^\d]', '', str(v or ''))
    return s.lstrip('0') or s


def load_sirh_json(json_path: str) -> pd.DataFrame:
    """
    Charge offres_sirh.json (format v4) et retourne un DataFrame normalisé.
    Compatible aussi avec le format v3 (champ detail imbriqué).

    Colonnes produites :
        N° AVE SIRH, _ave_key,
        Grand service SIRH, Poste SIRH, Unité SIRH, Emploi SIRH,
        Filière SIRH, Métier SIRH, Type poste SIRH,
        Corps SIRH, Restrictions grades, Vacance SIRH,
        Définition, Tâches, Commentaires, Profil,
        Responsable nom, Responsable tél, Responsable email
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f'Fichier introuvable : {json_path}')

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list) or len(data) == 0:
        raise ValueError('Le fichier JSON est vide ou mal formaté.')

    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue

        # ── N° AVE ──────────────────────────────────────────────────────────
        # v4 : clé normalisée ; v3 (compat) : clé brute
        ave = str(
            item.get('n_de_l_ave') or item.get("Numéro d'AVE") or ''
        ).strip()
        if not ave:
            continue

        # ── Responsable (peut être un dict ou absent) ────────────────────────
        resp = item.get('responsable') or {}
        if not isinstance(resp, dict):
            resp = {}

        # ── Restrictions de grade ────────────────────────────────────────────
        # v4 : chaîne de texte directe. v3 (compat) : dict JSON.
        restrictions_raw = item.get('restrictions_grades') or ''
        if isinstance(restrictions_raw, dict):
            restr_str = ' | '.join(f'{k}: {v}' for k, v in restrictions_raw.items())
        elif isinstance(restrictions_raw, str):
            restr_str = restrictions_raw.strip()
        else:
            restr_str = ''
        # Ajouter les restrictions IESSA / ICNA si présentes
        for corps_field in ('iessa', 'icna'):
            val = str(item.get(corps_field) or '').strip()
            if val:
                label = corps_field.upper()
                restr_str = f'{restr_str} | {label}: {val}' if restr_str else f'{label}: {val}'

        # ── Compatibilité v3 (champ detail imbriqué) ─────────────────────────
        detail_v3 = item.get('detail') or {}
        if isinstance(detail_v3, dict) and not detail_v3.get('erreur'):
            corps_v3 = detail_v3.get('corps', '')
            restr_v3 = detail_v3.get('restriction_grade', '')
        else:
            corps_v3 = restr_v3 = ''

        row = {
            'N° AVE SIRH':        ave,
            '_ave_key':           _norm_ave(ave),
            # Identification
            'Grand service SIRH': str(item.get('grand_service') or item.get('Grand service') or '').strip(),
            'Poste SIRH':         str(item.get('poste') or item.get('Poste') or item.get('libelle_de_l_ave') or '').strip(),
            'Unité SIRH':         str(item.get('unite_organisationnelle') or item.get('Unité organisationnelle') or '').strip(),
            'Emploi SIRH':        str(item.get('emploi') or item.get('Emploi') or '').strip(),
            'Filière SIRH':       str(item.get('filiere') or '').strip(),
            'Métier SIRH':        str(item.get('metier') or '').strip(),
            'Type poste SIRH':    str(item.get('type_de_poste') or '').strip(),
            'Personne remplacée': str(item.get('personne_remplacee') or '').strip(),
            'Nb postes SIRH':     str(item.get('nombre_de_poste') or '').strip(),
            # Corps
            'Corps SIRH':         str(item.get('corps_liste') or item.get('Ouverts au(x) corp(s)') or corps_v3 or '').strip(),
            'Restrictions grades': restr_str or restr_v3,
            # Vacance
            'Vacance SIRH':       str(item.get('vacance_immediate_eventuelle') or item.get('Vacance') or '').strip(),
            # Texte libre
            'Définition':         str(item.get('definition') or '').strip(),
            'Tâches':             str(item.get('taches') or '').strip(),
            'Commentaires':       str(item.get('commentaires') or '').strip(),
            'Profil':             str(item.get('profil_qualification') or '').strip(),
            # Responsable — v4 : champs au niveau racine ; v3 (compat) : sous-objet 'responsable'
            'Responsable nom':    str(item.get('nom') or resp.get('nom') or '').strip(),
            'Responsable tél':    str(item.get('numero_de_telephone') or resp.get('numero_de_telephone') or resp.get('tel') or '').strip(),
            'Responsable email':  str(item.get('adresse_electronique') or resp.get('adresse_electronique') or resp.get('email') or '').strip(),
            # Champ additif/modificatif
            'Additif/Modificatif': str(item.get('additif_modificatif') or '').strip(),
        }
        rows.append(row)

    if not rows:
        raise ValueError('Aucune offre valide trouvée dans le fichier JSON.')

    return pd.DataFrame(rows)


def merge_sirh_into_ave(df_ave: pd.DataFrame, df_sirh: pd.DataFrame) -> pd.DataFrame:
    """
    Enrichit df_ave avec les données SIRH via jointure sur N° AVE.
    Ajoute la colonne 'sirh_ok' (True si présent dans le SIRH).
    """
    ave  = df_ave.copy()
    sirh = df_sirh.copy()

    ave['_ave_key']  = ave['N° AVE'].apply(_norm_ave)
    sirh = sirh.drop_duplicates(subset=['_ave_key'])

    cols_to_join = [c for c in sirh.columns if c not in ('N° AVE SIRH', '_ave_key')]
    merged = ave.merge(sirh[['_ave_key'] + cols_to_join], on='_ave_key', how='left')

    merged['sirh_ok'] = (
        merged['Grand service SIRH'].notna() &
        (merged['Grand service SIRH'] != '')
    )
    merged = merged.drop(columns=['_ave_key'])
    return merged


def sirh_stats(df_sirh: pd.DataFrame) -> dict:
    """Retourne des statistiques sur les données SIRH importées."""
    total     = len(df_sirh)
    with_def  = int((df_sirh['Définition'].str.len() > 0).sum())
    with_resp = int((df_sirh['Responsable email'].str.len() > 0).sum())
    gs_counts = (
        df_sirh['Grand service SIRH']
        .value_counts()
        .head(15)
        .to_dict()
    )
    return {
        'total':        total,
        'with_detail':  with_def,
        'with_contact': with_resp,
        'gs_counts':    gs_counts,
    }
