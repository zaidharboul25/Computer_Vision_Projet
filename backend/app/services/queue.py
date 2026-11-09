"""File d'attente et worker séquentiel d'inspection textile (Phase 3).

Garantit :
- L'exécution strictement séquentielle (1 worker) pour maîtriser la charge CPU/RAM.
- Une file bornée (MAX_QUEUE) renvoyant SERVER_BUSY (503) en cas de saturation (Exigence G).
- La mise à jour en temps réel de la progression par moteur (pending -> running -> ok / error) (Exigence H).
- La résilience aux pannes partielles (aucun résultat inventé, signalement partial=True).
- Le redressement des boîtes en repère de l'image stockée (AC-02).
- La génération et persistance de la Heatmap 8-bit et de l'Overlay (AC-03).
- Le nettoyage au démarrage des inspections interrompues par redémarrage.
"""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image
from app.core.config import settings
from app.core.errors import ServerBusyException
from app.core.logging import logger
from app.db.repositories.inspections import InspectionRepository
from app.db.repositories.regions import RegionRepository
from app.engines.fusion import fuse_regions
from app.engines.registry import engine_registry
from app.engines.similarity_engine import SimilarityEngine
from app.services.storage import StorageService
from app.services.visualizer import VisualizerService


def evaluate_domain_bias(
    image: Image.Image,
    existing_wg_result: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Évalue la représentativité de l'image par rapport aux données d'apprentissage WeaveGuard (§5.3).

    Aide à l'interprétation (pas un verdict ni un filtre).
    Le seuil n'est PAS codé en dur : il est extrait dynamiquement de models/domain_bias_report_v1.json.
    """
    report_path = settings.get_models_dir() / "domain_bias_report_v1.json"
    reference_min = 0.8124
    if report_path.exists():
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                rep_data = json.load(f)
            quantiles = rep_data.get("familiarity_quantiles", [])
            if quantiles:
                reference_min = round(float(quantiles[0]), 4)
        except Exception as e:
            logger.warning(f"Impossible de lire le seuil de référence dans {report_path} : {e}")

    sim_engine = engine_registry.get_engine("similarity")
    if not isinstance(sim_engine, SimilarityEngine) or not engine_registry.is_engine_available("similarity"):
        return {
            "max_similarity": None,
            "reference_min": reference_min,
            "reference_source": "models/domain_bias_report_v1.json",
            "status": "unavailable",
        }, None

    try:
        if existing_wg_result and "results" in existing_wg_result and existing_wg_result["results"]:
            max_sim = float(existing_wg_result["results"][0]["score"])
        else:
            sim_res = sim_engine.search(image, index_name="weaveguard", k=1)
            results = sim_res.get("results", [])
            if not results:
                return {
                    "max_similarity": None,
                    "reference_min": reference_min,
                    "reference_source": "models/domain_bias_report_v1.json",
                    "status": "unavailable",
                }, None
            max_sim = float(results[0]["score"])

        max_sim = round(max_sim, 4)
        if max_sim < reference_min:
            warning_msg = (
                f"Cette image ressemble peu aux images d'apprentissage "
                f"(similarité maximale {max_sim:.4f}, minimum observé en validation/test {reference_min:.4f}). "
                f"Les résultats peuvent être moins fiables."
            )
            return {
                "max_similarity": max_sim,
                "reference_min": reference_min,
                "reference_source": "models/domain_bias_report_v1.json",
                "status": "below_range",
            }, warning_msg
        else:
            return {
                "max_similarity": max_sim,
                "reference_min": reference_min,
                "reference_source": "models/domain_bias_report_v1.json",
                "status": "in_range",
            }, None

    except Exception as e:
        logger.warning(f"Échec de l'évaluation du biais de domaine : {e}")
        return {
            "max_similarity": None,
            "reference_min": reference_min,
            "reference_source": "models/domain_bias_report_v1.json",
            "status": "unavailable",
        }, None


def assign_display_ids(fused_regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attribue un identifiant court d'affichage display_id déterministe :
    Y1, Y2... pour YOLO (par ordre de confiance décroissante)
    P1, P2... pour PatchCore (par ordre de score décroissant)
    """
    yolo_regs = [r for r in fused_regions if (r.get("source_engine") or r.get("engine")) == "yolo"]
    pc_regs = [r for r in fused_regions if (r.get("source_engine") or r.get("engine")) == "patchcore"]

    yolo_regs.sort(
        key=lambda r: (float(r.get("score") if r.get("score") is not None else 0.0), -r["bbox"][1], -r["bbox"][0]),
        reverse=True,
    )
    pc_regs.sort(
        key=lambda r: (float(r.get("score") if r.get("score") is not None else 0.0), -r["bbox"][1], -r["bbox"][0]),
        reverse=True,
    )

    for idx, r in enumerate(yolo_regs, start=1):
        r["display_id"] = f"Y{idx}"

    for idx, r in enumerate(pc_regs, start=1):
        r["display_id"] = f"P{idx}"

    return yolo_regs + pc_regs


class InspectionTask:
    def __init__(
        self,
        inspection_id: str,
        stored_image: Image.Image,
        inference_image: Image.Image,
        resize_factor: float,
        selected_engines: List[str],
    ):
        self.inspection_id = inspection_id
        self.stored_image = stored_image
        self.inference_image = inference_image
        self.resize_factor = resize_factor
        self.selected_engines = selected_engines


class InspectionWorker:
    def __init__(self):
        self._queue: Optional[asyncio.Queue[InspectionTask]] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    def initialize(self) -> None:
        """Initialise la file d'attente bornée."""
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=settings.MAX_QUEUE)

    async def start(self) -> None:
        """Démarre le worker en arrière-plan et nettoie les orphelins (Exigence G)."""
        self.initialize()
        if self._worker_task is None or self._worker_task.done():
            # Nettoyage des inspections orphelines interrompues par redémarrage
            orphans_cleaned = await InspectionRepository.cleanup_orphan_inspections()
            if orphans_cleaned > 0:
                logger.warning(
                    f"{orphans_cleaned} inspection(s) orpheline(s) passée(s) en erreur suite au démarrage du serveur."
                )

            self._running = True
            self._worker_task = asyncio.create_task(self._process_queue_loop())
            logger.info(f"Worker d'inspection séquentiel démarré (taille max file : {settings.MAX_QUEUE}).")

    async def stop(self) -> None:
        """Arrête proprement le worker."""
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Worker d'inspection arrêté.")

    async def enqueue(
        self,
        inspection_id: str,
        stored_image: Image.Image,
        inference_image: Image.Image,
        resize_factor: float,
        selected_engines: List[str],
    ) -> None:
        """Enfile une nouvelle tâche d'inspection. Lève SERVER_BUSY si la file est pleine."""
        self.initialize()
        assert self._queue is not None

        if self._queue.full():
            logger.warning(f"File d'inspection saturée ({self._queue.qsize()}/{settings.MAX_QUEUE}). Rejet 503.")
            raise ServerBusyException()

        task = InspectionTask(
            inspection_id=inspection_id,
            stored_image=stored_image,
            inference_image=inference_image,
            resize_factor=resize_factor,
            selected_engines=selected_engines,
        )

        try:
            self._queue.put_nowait(task)
        except asyncio.QueueFull:
            raise ServerBusyException()

    async def _process_queue_loop(self) -> None:
        """Boucle de traitement séquentielle."""
        assert self._queue is not None
        while self._running:
            try:
                task = await self._queue.get()
                try:
                    await self._execute_inspection(task)
                except Exception as e:
                    logger.error(f"Erreur inattendue dans le worker d'inspection {task.inspection_id} : {e}")
                    await InspectionRepository.complete_inspection(
                        inspection_id=task.inspection_id,
                        status="error",
                        partial=False,
                        regions_count=0,
                        error_message=f"Erreur interne d'exécution : {str(e)}",
                    )
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur fatale dans la boucle du worker : {e}")
                await asyncio.sleep(1)

    async def _execute_inspection(self, task: InspectionTask) -> None:
        """Exécute l'inspection complète d'une tâche avec mise à jour en temps réel."""
        inspection_id = task.inspection_id
        await InspectionRepository.update_status(inspection_id, status="running")

        # Callback thread-safe pour mettre à jour la base MongoDB au fur et à mesure (Exigence H)
        main_loop = asyncio.get_running_loop()

        def progress_callback(engine_name: str, status: str, version: Optional[str] = None, error: Optional[str] = None):
            asyncio.run_coroutine_threadsafe(
                InspectionRepository.update_engine_progress(
                    inspection_id=inspection_id,
                    engine_name=engine_name,
                    status=status,
                    version=version,
                    error=error,
                ),
                main_loop,
            )

        # Exécution du pipeline dans le threadpool pour ne pas bloquer l'event loop asyncio
        pipeline_result = await main_loop.run_in_executor(
            None,
            lambda: engine_registry.run_pipeline(
                task.inference_image,
                selected_engines=task.selected_engines,
                progress_callback=progress_callback,
            ),
        )

        # Enregistrement des latences finales par moteur dans MongoDB
        engines_out = pipeline_result.get("engines", {})
        for eng_name, eng_res in engines_out.items():
            latency_data = eng_res.get("latency")
            await InspectionRepository.update_engine_progress(
                inspection_id=inspection_id,
                engine_name=eng_name,
                status=eng_res.get("status", "ok"),
                error=eng_res.get("error"),
                latency_ms=latency_data,
            )

        # Gestion des résultats et rééchelonnage des coordonnées (AC-02)
        scale = task.resize_factor
        raw_yolo_regions = engines_out.get("yolo", {}).get("regions", [])
        raw_pc_regions = engines_out.get("patchcore", {}).get("regions", [])
        pc_raw_data = engines_out.get("patchcore", {}).get("raw_data", {})

        # Remappage des boîtes vers les coordonnées de l'image originale stockée
        def rescale_region(r: Dict[str, Any]) -> Dict[str, Any]:
            rx, ry, rw, rh = r["bbox"]
            mapped_box = [
                round(rx / scale, 2),
                round(ry / scale, 2),
                round(rw / scale, 2),
                round(rh / scale, 2),
            ]
            area = round((rw / scale) * (rh / scale), 2)
            reg_copy = dict(r)
            reg_copy["bbox"] = mapped_box
            reg_copy["area"] = area
            return reg_copy

        scaled_yolo = [rescale_region(r) for r in raw_yolo_regions]
        scaled_pc = [rescale_region(r) for r in raw_pc_regions]

        # Fusion géométrique selon la spécification (§6 & fusion_spec.json)
        fused_regions = fuse_regions(scaled_yolo, scaled_pc)

        # Attribution d'un identifiant court d'affichage display_id déterministe
        sorted_regions = assign_display_ids(fused_regions)

        # Attribution d'un UUID unique immuable à chaque région persistée
        db_regions = []
        for reg in sorted_regions:
            reg_id = str(uuid.uuid4())
            engine_name = reg.get("source_engine") or reg.get("engine", "yolo")
            corro_raw = reg.get("corroboration")
            if corro_raw:
                corro_info = {
                    "detected": True,
                    "overlap_ratio_box": None,
                    "overlap_ratio_region": None,
                    "score_patchcore": corro_raw.get("score"),
                    "tau_patchcore": corro_raw.get("threshold"),
                }
            else:
                corro_info = None

            db_regions.append({
                "id": reg_id,
                "display_id": reg.get("display_id"),
                "inspection_id": inspection_id,
                "engine": engine_name,
                "bbox": reg["bbox"],
                "area": reg["area"],
                "label": reg["label"],
                "score": reg.get("score"),
                "classification": reg.get("classification"),
                "tau": reg.get("tau") or reg.get("score_threshold"),
                "corroboration": corro_info,
                "created_at": datetime.now(timezone.utc),
            })

        # Persistance immuable des régions
        await RegionRepository.bulk_create_regions(db_regions)

        # Gestion de la heatmap si PatchCore a produit un score map
        heatmap_meta_dict = None
        if "score_map" in pc_raw_data:
            raw_map = pc_raw_data["score_map"]
            tau_val = pc_raw_data.get("tau_global", 1.6386)

            # Sauvegarde de la carte brute float32
            StorageService.save_raw_map(inspection_id, raw_map)

            # Génération et sauvegarde de la heatmap PNG 8 bits
            heatmap_img, heatmap_meta = VisualizerService.generate_heatmap(
                raw_score_map=raw_map,
                stored_size=(task.stored_image.width, task.stored_image.height),
                tau=tau_val,
            )
            StorageService.save_heatmap_png(inspection_id, heatmap_img)
            heatmap_meta_dict = heatmap_meta.model_dump()

        # Génération et sauvegarde de l'overlay à partir des régions lues / formatées (AC-03)
        overlay_img = VisualizerService.generate_overlay(task.stored_image, db_regions)
        StorageService.save_overlay_png(inspection_id, overlay_img)

        # Évaluation du biais de domaine / représentativité (aide à l'interprétation, pas un verdict ni un filtre)
        existing_wg = engines_out.get("similarity", {}).get("raw_data", {}).get("weaveguard")
        domain_check, domain_warning = await main_loop.run_in_executor(
            None,
            lambda: evaluate_domain_bias(task.inference_image, existing_wg_result=existing_wg),
        )

        # Récupération des warnings existants et ajout de l'avertissement hors domaine éventuel
        inspection_doc = await InspectionRepository.get_by_id(inspection_id)
        current_warnings = list(
            (inspection_doc or {}).get(
                "warnings",
                (inspection_doc or {}).get("image_meta", {}).get("warnings", []),
            )
        )
        if domain_warning and domain_warning not in current_warnings:
            current_warnings.append(domain_warning)

        # Détermination du statut global et partialité
        statuses = [res.get("status") for res in engines_out.values()]
        all_failed = all(s == "error" for s in statuses)
        any_failed = any(s == "error" for s in statuses)

        final_status = "error" if all_failed else "done"
        is_partial = any_failed and not all_failed
        err_msg = "Tous les moteurs d'inférence ont échoué" if all_failed else None

        await InspectionRepository.complete_inspection(
            inspection_id=inspection_id,
            status=final_status,
            partial=is_partial,
            regions_count=len(db_regions),
            heatmap_meta=heatmap_meta_dict,
            error_message=err_msg,
            domain_check=domain_check,
            warnings=current_warnings,
        )


inspection_worker = InspectionWorker()
