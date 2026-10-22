#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
secret_store.py — Stockage chiffré du token Netlify.

Le token est chiffré avec un « mot de passe de publication » (dérivation
PBKDF2-SHA256 + chiffrement Fernet / AES). Le fichier chiffré peut être
partagé (dossier OneDrive) : sans le mot de passe, il est illisible.
Le mot de passe n'est jamais enregistré.
"""

import base64
import json
import os
from pathlib import Path

ITERATIONS = 600_000


class SecretError(Exception):
    pass


def _fernet(password: str, salt: bytes, iterations: int):
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError:
        raise SecretError("Module « cryptography » manquant : relancez installer.bat.")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=iterations)
    key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
    return Fernet(key)


def has_token(path: Path) -> bool:
    return Path(path).is_file()


def save_token(path: Path, token: str, password: str) -> None:
    """Chiffre `token` avec `password` et l'écrit dans `path`."""
    path = Path(path)
    salt = os.urandom(16)
    data = {
        "version":    1,
        "kdf":        "pbkdf2-sha256",
        "iterations": ITERATIONS,
        "salt":       base64.b64encode(salt).decode("ascii"),
        "token":      _fernet(password, salt, ITERATIONS)
                          .encrypt(token.encode("utf-8")).decode("ascii"),
    }
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_token(path: Path, password: str) -> str:
    """Déchiffre le token. Lève SecretError si le mot de passe est faux."""
    path = Path(path)
    if not path.is_file():
        raise SecretError("Aucun token Netlify enregistré (Paramètres).")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        salt = base64.b64decode(data["salt"])
        iterations = int(data.get("iterations", ITERATIONS))
        blob = data["token"].encode("ascii")
    except Exception:
        raise SecretError("Fichier du token illisible : ressaisissez le token dans Paramètres.")
    f = _fernet(password, salt, iterations)
    try:
        from cryptography.fernet import InvalidToken
        return f.decrypt(blob).decode("utf-8")
    except InvalidToken:
        raise SecretError("Mot de passe de publication incorrect.")
