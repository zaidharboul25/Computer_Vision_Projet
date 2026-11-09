"""Client asynchrone MongoDB officiel (AsyncMongoClient) pour WeaveGuard AI.

Gère la connexion, le démarrage dégradé si MongoDB est indisponible,
le ping de santé et la mise à disposition de la base de données.
"""
from typing import Optional
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from app.core.config import settings
from app.core.errors import DatabaseUnavailableException
from app.core.logging import logger


class MongoManager:
    def __init__(self):
        self.client: Optional[AsyncMongoClient] = None
        self.db: Optional[AsyncDatabase] = None
        self.is_connected: bool = False
        self.last_error: Optional[str] = None

    async def connect(self, timeout_ms: int = 2000) -> bool:
        """Tente de se connecter à MongoDB et vérifie avec un ping."""
        try:
            self.client = AsyncMongoClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=timeout_ms,
                connectTimeoutMS=timeout_ms,
            )
            self.db = self.client[settings.DB_NAME]
            # Vérification réelle par ping
            await self.client.admin.command("ping")
            self.is_connected = True
            self.last_error = None
            logger.info(f"Connexion MongoDB réussie à {settings.MONGODB_URI}/{settings.DB_NAME}")
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
            self.is_connected = False
            self.last_error = str(e)
            logger.warning(
                f"MongoDB indisponible au démarrage ({e}). Démarrage en mode dégradé."
            )
            return False

    async def ping(self) -> bool:
        """Teste la réactivité du serveur MongoDB."""
        if not self.client:
            return False
        try:
            await self.client.admin.command("ping")
            self.is_connected = True
            self.last_error = None
            return True
        except Exception as e:
            self.is_connected = False
            self.last_error = str(e)
            return False

    def get_database(self) -> AsyncDatabase:
        """Retourne la base de données active ou lève DatabaseUnavailableException."""
        if not self.is_connected or self.db is None:
            raise DatabaseUnavailableException(
                message="Base de données MongoDB inaccessible",
                details={"uri": settings.MONGODB_URI, "error": self.last_error},
            )
        return self.db

    async def close(self) -> None:
        if self.client:
            await self.client.close()
            self.is_connected = False
            logger.info("Connexion MongoDB fermée.")


mongo_manager = MongoManager()


def get_db() -> AsyncDatabase:
    """Dépendance FastAPI pour injecter la base de données."""
    return mongo_manager.get_database()


def get_database() -> AsyncDatabase:
    """Accesseur standard pour obtenir la base active."""
    return mongo_manager.get_database()


