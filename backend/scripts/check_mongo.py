#!/usr/bin/env python
"""
Diagnostic et vérification de la connexion MongoDB locale sous Windows.
Vérifie le ping, la version du serveur, l'accès à la base weaveguard
et assure la création idempotente des index.
Usage:
    python backend/scripts/check_mongo.py
"""
import asyncio
import sys
from pathlib import Path

# Ajout du répertoire backend au chemin Python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymongo import AsyncMongoClient
from app.core.config import settings
from app.db.indexes import ensure_indexes


async def check_mongo() -> bool:
    print("=" * 65)
    print(" WeaveGuard AI - Diagnostic MongoDB local (Windows)")
    print("=" * 65)
    print(f"URI cible    : {settings.MONGODB_URI}")
    print(f"Base cible   : {settings.DB_NAME}")

    client = AsyncMongoClient(
        settings.MONGODB_URI,
        serverSelectionTimeoutMS=2500,
        connectTimeoutMS=2500,
    )

    try:
        # 1. Ping
        print("\n1. Test de connectivité (Ping)...")
        ping_res = await client.admin.command("ping")
        print(f"   [SUCCÈS] Ping MongoDB réussi : {ping_res}")

        # 2. Informations du serveur
        print("\n2. Informations du serveur...")
        build_info = await client.admin.command("buildInfo")
        print(f"   - Version MongoDB : {build_info.get('version')}")
        print(f"   - Système         : {build_info.get('sysInfo', 'Windows')}")

        # 3. Vérification de la base et des index
        print(f"\n3. Vérification de la base '{settings.DB_NAME}' et création des index...")
        db = client[settings.DB_NAME]
        await ensure_indexes(db)
        print("   [SUCCÈS] Tous les index sont synchronisés et conformes.")

        print("\n" + "=" * 65)
        print(" [OK] MongoDB est pleinement opérationnel pour WeaveGuard AI.")
        print("=" * 65)
        return True

    except Exception as e:
        print(f"\n[ÉCHEC] Impossible de joindre le serveur MongoDB : {e}")
        print("-" * 65)
        print("AIDE AU DÉPANNAGE SOUS WINDOWS :")
        print("1. Le service Windows MongoDB est-il démarré ?")
        print("   Dans PowerShell (administrateur) :")
        print("   > Get-Service MongoDB")
        print("   > Start-Service MongoDB")
        print("2. Le port 27017 est-il libre et à l'écoute ?")
        print("   > Test-NetConnection -ComputerName 127.0.0.1 -Port 27017")
        print("3. Si vous avez configuré une authentification, vérifiez")
        print("   la variable MONGODB_URI dans votre fichier .env.")
        print("=" * 65)
        return False

    finally:
        await client.close()


if __name__ == "__main__":
    success = asyncio.run(check_mongo())
    sys.exit(0 if success else 1)

