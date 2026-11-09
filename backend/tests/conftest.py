"""Fixtures pytest pour les tests du backend WeaveGuard AI."""
from typing import AsyncGenerator
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pymongo import AsyncMongoClient

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.indexes import ensure_indexes
from app.db.mongo import mongo_manager
from app.main import app

TEST_DB_NAME = "weaveguard_test"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Initialise un client MongoDB lié à la boucle d'événements du test en cours."""
    settings.DB_NAME = TEST_DB_NAME
    client = AsyncMongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=3000)
    db = client[TEST_DB_NAME]

    # Réinitialisation propre des index et collections pour éviter les résidus d'anciennes phases
    for col_name in ["users", "inspections", "regions", "feedback", "audit_log", "settings"]:
        try:
            await db[col_name].drop_indexes()
        except Exception:
            pass
        await db[col_name].delete_many({})

    await ensure_indexes(db)

    # Branchement de mongo_manager sur la base de test pour ce test
    mongo_manager.client = client
    mongo_manager.db = db
    mongo_manager.is_connected = True

    yield db

    # Nettoyage après test
    for col_name in ["users", "inspections", "regions", "feedback", "audit_log", "settings"]:
        await db[col_name].delete_many({})

    # Nettoyage des fichiers temporaires créés dans le stockage de test
    test_storage_insp = settings.get_storage_dir() / "inspections"
    if test_storage_insp.exists():
        import shutil
        for folder in test_storage_insp.iterdir():
            if folder.is_dir():
                shutil.rmtree(folder, ignore_errors=True)

    await client.close()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Client HTTP asynchrone pour interroger l'application FastAPI."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def create_user_helper(setup_test_db):
    """Fabrique d'utilisateurs de test enregistrés en base."""
    db = setup_test_db

    async def _create(username: str, role: str, password: str = "TestPass123!", active: bool = True):
        import uuid
        from datetime import datetime, timezone

        doc = {
            "_id": str(uuid.uuid4()),
            "username": username,
            "password_hash": hash_password(password),
            "role": role,
            "active": active,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None,
            "failed_attempts": 0,
            "locked_until": None,
        }
        await db.users.insert_one(doc)
        token = create_access_token(subject=username, role=role)
        return doc, token

    return _create


@pytest_asyncio.fixture
async def admin_auth(create_user_helper):
    user, token = await create_user_helper("admin_test", "admin")
    return {"user": user, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


@pytest_asyncio.fixture
async def operator_auth(create_user_helper):
    user, token = await create_user_helper("operator_test", "operator")
    return {"user": user, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


@pytest_asyncio.fixture
async def supervisor_auth(create_user_helper):
    user, token = await create_user_helper("supervisor_test", "supervisor")
    return {"user": user, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


@pytest_asyncio.fixture
async def ml_engineer_auth(create_user_helper):
    user, token = await create_user_helper("ml_test", "ml_engineer")
    return {"user": user, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


@pytest_asyncio.fixture
async def auditor_auth(create_user_helper):
    user, token = await create_user_helper("auditor_test", "auditor")
    return {"user": user, "token": token, "headers": {"Authorization": f"Bearer {token}"}}
