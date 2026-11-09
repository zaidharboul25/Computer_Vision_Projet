#!/usr/bin/env python
"""
Création interactive du compte administrateur initial.
Par défaut, saisie masquée au clavier avec validation de la politique minimale (12 caractères).
L'option --password est strictement réservée aux tests automatisés.

Usage interactif :
    python backend/scripts/create_admin.py
Usage automatisé (tests uniquement) :
    python backend/scripts/create_admin.py --username admin --password "..."
"""
import argparse
import asyncio
import getpass
import sys
from pathlib import Path

# Ajout du répertoire backend au chemin Python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymongo import AsyncMongoClient
from app.core.config import settings
from app.core.permissions import UserRole
from app.core.security import hash_password
from app.db.repositories.audit import AuditRepository
from app.db.repositories.users import UserRepository

MIN_PASSWORD_LENGTH = 12


async def create_or_update_admin(username: str, password: str) -> bool:
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"[ERREUR] Le mot de passe doit comporter au moins {MIN_PASSWORD_LENGTH} caractères.")
        return False

    client = AsyncMongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=3000)
    try:
        db = client[settings.DB_NAME]
        user_repo = UserRepository(db)
        audit_repo = AuditRepository(db)

        existing = await user_repo.get_by_username(username)
        if existing:
            print(f"[ATTENTION] L'utilisateur '{username}' existe déjà (rôle: {existing.get('role')}).")
            confirm = input("Voulez-vous réinitialiser son mot de passe et lui attribuer le rôle admin ? (o/n) : ")
            if confirm.lower() not in ("o", "oui", "y", "yes"):
                print("Opération annulée.")
                return False

            new_hash = hash_password(password)
            await user_repo.update(
                existing["_id"],
                {
                    "password_hash": new_hash,
                    "role": UserRole.ADMIN.value,
                    "active": True,
                    "failed_attempts": 0,
                    "locked_until": None,
                },
            )
            await audit_repo.log_action(
                action="admin_updated_via_script",
                details={"username": username},
            )
            print(f"[SUCCÈS] Le compte '{username}' a été mis à jour avec le rôle 'admin'.")
            return True
        else:
            user = await user_repo.create(
                username=username,
                password=password,
                role=UserRole.ADMIN.value,
            )
            await audit_repo.log_action(
                action="admin_created_via_script",
                user_id=user["_id"],
                details={"username": username},
            )
            print(f"[SUCCÈS] Administrateur '{username}' créé avec succès (ID: {user['_id']}).")
            return True
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description="Création de l'administrateur WeaveGuard AI")
    parser.add_argument("--username", "-u", type=str, default=None, help="Nom d'utilisateur")
    parser.add_argument("--password", "-p", type=str, default=None, help="Mot de passe (réservé aux tests automatisés)")
    args = parser.parse_args()

    username = args.username
    password = args.password

    if not username:
        username = input("Nom d'utilisateur admin [admin] : ").strip() or "admin"

    if not password:
        while True:
            p1 = getpass.getpass(f"Mot de passe (minimum {MIN_PASSWORD_LENGTH} caractères) : ")
            if len(p1) < MIN_PASSWORD_LENGTH:
                print(f"Le mot de passe doit comporter au moins {MIN_PASSWORD_LENGTH} caractères.")
                continue
            p2 = getpass.getpass("Confirmez le mot de passe : ")
            if p1 != p2:
                print("Les mots de passe ne correspondent pas. Réessayez.")
                continue
            password = p1
            break

    asyncio.run(create_or_update_admin(username, password))


if __name__ == "__main__":
    main()
