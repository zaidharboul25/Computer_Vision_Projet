"""Point d'entrée principal de l'API WeaveGuard AI."""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match, Mount
from starlette.staticfiles import StaticFiles

from app.core.config import settings
from app.core.correlation import CorrelationIdMiddleware
from app.core.errors import (
    AppException,
    app_exception_handler,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.logging import logger, setup_logging
from app.db.indexes import ensure_indexes
from app.db.mongo import mongo_manager
from app.api.v1.auth import router as auth_router
from app.api.v1.audit import router as audit_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.health import router as health_router
from app.api.v1.inspections import router as inspections_router
from app.api.v1.models import router as models_router
from app.api.v1.regions import router as regions_router
from app.api.v1.similarity import router as similarity_router
from app.api.v1.settings import router as settings_router
from app.api.v1.stats import router as stats_router
from app.api.v1.users import router as users_router
from app.services.queue import inspection_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarrage
    setup_logging()
    logger.info(f"Démarrage de WeaveGuard AI (ENV={settings.ENV})")

    # Validation stricte des chemins d'artefacts
    artifact_errors = settings.validate_artifact_paths()
    if artifact_errors:
        for err in artifact_errors:
            logger.error(err)
        if settings.ENV in ("validation", "prod"):
            raise RuntimeError(f"Échec critique : artefacts manquants ({len(artifact_errors)})")

    # Connexion MongoDB
    db_connected = await mongo_manager.connect()
    if db_connected and mongo_manager.db is not None:
        await ensure_indexes(mongo_manager.db)
        # Démarrage du worker d'inspection (nettoie aussi les orphelins interrompus)
        await inspection_worker.start()

        # Échauffement initial asynchrone des moteurs IA (élimine le pic de cold-start)
        async def _warmup_engines():
            try:
                from PIL import Image
                from app.engines.registry import engine_registry
                dummy = Image.new("RGB", (640, 640), (128, 128, 128))
                loop = asyncio.get_running_loop()
                for eng_name in ("yolo", "patchcore", "similarity"):
                    if engine_registry.is_engine_available(eng_name):
                        eng = engine_registry.get_engine(eng_name)
                        if eng:
                            await loop.run_in_executor(None, lambda: eng.infer(dummy))
                logger.info("Warmup initial des moteurs IA terminé avec succès.")
            except Exception as e:
                logger.warning(f"Échec de l'échauffement initial des moteurs : {e}")

        asyncio.create_task(_warmup_engines())
    else:
        logger.warning("MongoDB n'a pas répondu. Le serveur reste accessible en mode dégradé (503 sur routes dépendantes).")

    yield

    # Arrêt
    logger.info("Arrêt de WeaveGuard AI...")
    await inspection_worker.stop()
    await mongo_manager.close()


class SPAStaticFiles(StaticFiles):
    """Sert les fichiers statiques du frontend avec fallback SPA.

    Pour toute URL non trouvée sur le disque (routes de navigation React comme /inspections),
    renvoie index.html afin que le routeur client prenne le relais.
    Ne capture jamais les routes API, santé ou documentation.
    """

    async def get_response(self, path: str, scope):
        norm_path = path.replace("\\", "/")
        if (
            norm_path == "api"
            or norm_path.startswith("api/")
            or norm_path == "health"
            or norm_path == "docs"
            or norm_path.startswith("docs/")
            or norm_path == "redoc"
            or norm_path == "openapi.json"
        ):
            raise StarletteHTTPException(status_code=404, detail="Not Found")

        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404:
            return await super().get_response("index.html", scope)
        return response


class SPAMount(Mount):
    """Montage Starlette n'interceptant jamais les routes API, santé et documentation."""

    def matches(self, scope):
        path = scope.get("path", "")
        if (
            path.startswith("/api")
            or path.startswith("/health")
            or path.startswith("/docs")
            or path.startswith("/redoc")
            or path == "/openapi.json"
        ):
            return Match.NONE, {}
        return super().matches(scope)


def create_app() -> FastAPI:
    app = FastAPI(
        title="WeaveGuard AI - API d'Inspection Textile",
        description="Plateforme de détection de défauts textiles par vision par ordinateur (YOLO, PatchCore, Similarité).",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Middlewares (ordre : corrélation d'abord, puis CORS)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "Content-Disposition"],
    )

    # Gestionnaires d'erreurs garantissant le format JSON contractuel
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Routes
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(inspections_router, prefix="/api/v1")
    app.include_router(regions_router, prefix="/api/v1")
    app.include_router(similarity_router, prefix="/api/v1")
    app.include_router(models_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(stats_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(feedback_router, prefix="/api/v1")

    # Montage des fichiers statiques du frontend avec fallback SPA
    frontend_dist = settings.get_frontend_dist_dir()
    if frontend_dist and (frontend_dist / "index.html").exists():
        logger.info(f"Frontend compilé détecté dans {frontend_dist}. Montage SPA sur /")
        app.routes.append(SPAMount("/", app=SPAStaticFiles(directory=frontend_dist, html=True), name="frontend"))
    else:
        logger.info("Aucun répertoire frontend/dist détecté. Mode API pure actif.")

    return app


app = create_app()

