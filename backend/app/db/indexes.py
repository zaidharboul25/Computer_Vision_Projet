"""Création idempotente des index MongoDB de WeaveGuard AI (§8)."""
from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase
from app.core.logging import logger


async def ensure_indexes(db: AsyncDatabase) -> None:
    """Crée les index requis de manière idempotente."""
    try:
        # Collection 'users'
        await db.users.create_index([("username", ASCENDING)], unique=True)

        # Collection 'inspections'
        await db.inspections.create_index([("id", ASCENDING)], unique=True)
        await db.inspections.create_index([("created_at", DESCENDING)])
        await db.inspections.create_index([("created_by", ASCENDING), ("created_at", DESCENDING)])
        await db.inspections.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
        await db.inspections.create_index([("is_demo", ASCENDING)])

        # Collection 'regions'
        await db.regions.create_index([("inspection_id", ASCENDING)])
        await db.regions.create_index([("engine", ASCENDING)])

        # Collection 'feedback' (historique en ajout seul, tri chronologique inverse déterministe)
        await db.feedback.create_index([("region_id", ASCENDING), ("seq", DESCENDING)])
        await db.feedback.create_index([("region_id", ASCENDING), ("created_at", DESCENDING)])
        await db.feedback.create_index([("inspection_id", ASCENDING)])

        # Collection 'audit_log'
        await db.audit_log.create_index([("at", DESCENDING)])
        await db.audit_log.create_index([("action", ASCENDING)])
        await db.audit_log.create_index([("user_id", ASCENDING)])

        logger.info("Index MongoDB vérifiés et synchronisés avec succès.")
    except Exception as e:
        logger.error(f"Erreur lors de la création des index MongoDB : {e}")
        raise

