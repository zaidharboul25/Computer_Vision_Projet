#!/usr/bin/env python
"""
Générateur de clé secrète cryptographique aléatoire pour JWT_SECRET.
Usage:
    python backend/scripts/generate_secret.py
"""
import secrets


def generate_secret() -> str:
    return secrets.token_hex(32)


if __name__ == "__main__":
    secret = generate_secret()
    print("Nouvelle clé aléatoire (256 bits / 64 caractères hexadécimaux) :")
    print(secret)

