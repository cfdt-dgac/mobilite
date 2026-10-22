#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
netlify_deploy.py
Déploiement du dossier site/ sur Netlify via leur API REST.
"""

import os
import hashlib
import zipfile
import tempfile
import requests
from pathlib import Path


NETLIFY_API = "https://api.netlify.com/api/v1"


class NetlifyError(Exception):
    pass


def _md5(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


def _zip_dir(site_dir: Path) -> str:
    """Crée un zip temporaire du dossier site/ et retourne son chemin."""
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in site_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(site_dir))
    return tmp.name


def get_sites(token: str) -> list[dict]:
    """Liste les sites Netlify du compte."""
    r = requests.get(
        f"{NETLIFY_API}/sites",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def deploy(site_dir: str, site_id: str, token: str) -> str:
    """
    Déploie le dossier `site_dir` sur le site Netlify `site_id`.
    Retourne l'URL du déploiement.
    """
    site_path = Path(site_dir)
    if not site_path.exists():
        raise NetlifyError(f"Dossier introuvable : {site_dir}")

    zip_path = _zip_dir(site_path)
    try:
        with open(zip_path, "rb") as f:
            data = f.read()

        r = requests.post(
            f"{NETLIFY_API}/sites/{site_id}/deploys",
            headers={
                "Authorization":  f"Bearer {token}",
                "Content-Type":   "application/zip",
            },
            data=data,
            timeout=120,
        )
        r.raise_for_status()
        result = r.json()
        return result.get("deploy_ssl_url") or result.get("ssl_url") or result.get("url", "")
    finally:
        os.unlink(zip_path)


def check_token(token: str) -> bool:
    """Vérifie qu'un token Netlify est valide."""
    try:
        r = requests.get(
            f"{NETLIFY_API}/user",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False
