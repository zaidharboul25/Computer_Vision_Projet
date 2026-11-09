"""Registre et orchestrateur des moteurs IA WeaveGuard AI (§5, NFR-06).

Gère le cycle de vie des moteurs, l'isolation stricte des pannes (une erreur
d'un moteur ne contamine pas les autres) et la notification de progression.
"""
from typing import Any, Callable, Dict, List, Optional
from PIL import Image

from app.core.config import settings
from app.core.logging import logger
from app.engines.base import BaseEngine, EngineResult
from app.engines.fusion import fuse_regions
from app.engines.patchcore_engine import PatchCoreEngine
from app.engines.similarity_engine import SimilarityEngine
from app.engines.yolo_engine import YOLOEngine


class EngineRegistry:
    def __init__(self):
        self._engines: Dict[str, BaseEngine] = {
            "yolo": YOLOEngine(),
            "patchcore": PatchCoreEngine(),
            "similarity": SimilarityEngine(),
        }

    def get_engine(self, name: str) -> Optional[BaseEngine]:
        return self._engines.get(name)

    def is_engine_available(self, name: str) -> bool:
        return name in self._engines and name in settings.ENGINES_ENABLED

    def get_all_info(self) -> Dict[str, Any]:
        info_dict = {}
        for name, engine in self._engines.items():
            if name in settings.ENGINES_ENABLED:
                try:
                    info_dict[name] = engine.info().model_dump()
                except Exception as e:
                    info_dict[name] = {"error": str(e)}
        return info_dict

    def get_all_health(self) -> Dict[str, Any]:
        health_dict = {}
        for name, engine in self._engines.items():
            if name in settings.ENGINES_ENABLED:
                try:
                    health_dict[name] = engine.health()
                except Exception as e:
                    health_dict[name] = {"status": "error", "message": str(e)}
        return health_dict

    def run_pipeline(
        self,
        image: Image.Image,
        selected_engines: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, str, Optional[str], Optional[str]], None]] = None,
    ) -> Dict[str, Any]:
        """Exécute les moteurs sélectionnés de façon séquentielle avec isolation stricte des erreurs."""
        if selected_engines is None:
            engines_to_run = [e for e in ["yolo", "patchcore", "similarity"] if e in settings.ENGINES_ENABLED]
        else:
            engines_to_run = [e for e in selected_engines if e in settings.ENGINES_ENABLED]

        # Initialisation de l'état "en attente" (pending) pour tous les moteurs sélectionnés
        for eng_name in engines_to_run:
            if progress_callback:
                progress_callback(eng_name, "pending", None, None)

        engine_results: Dict[str, EngineResult] = {}

        for eng_name in engines_to_run:
            engine = self._engines.get(eng_name)
            if not engine:
                continue

            # Notification : en cours (running)
            if progress_callback:
                progress_callback(eng_name, "running", None, None)

            try:
                logger.info(f"Démarrage de l'inférence moteur : {eng_name}")
                res = engine.infer(image)
                engine_results[eng_name] = res

                info = engine.get_info()
                # Notification : ok
                if progress_callback:
                    progress_callback(eng_name, "ok", info.version, None)

            except Exception as e:
                logger.exception(f"Erreur isolée dans le moteur {eng_name} : {e}")
                err_result = EngineResult(
                    engine_name=eng_name,
                    status="error",
                    error_message=str(e),
                )
                engine_results[eng_name] = err_result

                # Notification : error
                if progress_callback:
                    progress_callback(eng_name, "error", None, str(e))

        # Fusion YOLO + PatchCore si les deux moteurs ont produit un résultat "ok"
        yolo_res = engine_results.get("yolo")
        pc_res = engine_results.get("patchcore")

        fused_regions: List[Dict[str, Any]] = []
        if yolo_res and yolo_res.status == "ok" and pc_res and pc_res.status == "ok":
            pc_engine: PatchCoreEngine = self._engines["patchcore"]  # type: ignore
            tau = pc_engine.tau_global
            fused_regions = fuse_regions(yolo_res.regions, pc_res.regions, tau=tau)
        elif yolo_res and yolo_res.status == "ok":
            fused_regions = list(yolo_res.regions)
        elif pc_res and pc_res.status == "ok":
            fused_regions = list(pc_res.regions)

        return {
            "engines": {name: res.model_dump() for name, res in engine_results.items()},
            "fused_regions": fused_regions,
        }


engine_registry = EngineRegistry()

