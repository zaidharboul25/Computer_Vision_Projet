"""Moteur YOLO v8n_640 supervisé pour la détection de défauts textiles (§5.1, AC-05, AC-06)."""
import json
import time
from typing import Any, Dict, List, Optional
from PIL import Image
from ultralytics import YOLO

from app.core.config import settings
from app.core.errors import ModelUnavailableException
from app.engines.base import BaseEngine, EngineInfo, EngineResult, LatencyBreakdown
from app.engines.integrity import IntegrityVerifier


class YOLOEngine(BaseEngine):
    def __init__(self):
        super().__init__(name="yolo")
        self.model: Optional[YOLO] = None
        self.device = settings.get_effective_device()
        self.card_data: Dict[str, Any] = {}
        self.classes: List[str] = []
        self.conf: float = 0.3113113113113113
        self.iou_nms: float = 0.6
        self.imgsz: int = 640
        self.weights_sha256: str = ""

    def load(self) -> None:
        valid, exp_hash, act_hash = IntegrityVerifier.verify_yolo_integrity()
        if not valid:
            raise ModelUnavailableException(
                message="Échec d'intégrité SHA-256 du modèle YOLO (best.pt)",
                details={"expected": exp_hash, "actual": act_hash},
            )
        self.weights_sha256 = act_hash

        card_path = settings.get_models_dir() / "weaveguard_yolo_v1" / "model_card.json"
        with open(card_path, "r", encoding="utf-8") as f:
            self.card_data = json.load(f)

        self.classes = self.card_data.get("classes", [])
        self.conf = float(self.card_data.get("conf_threshold", {}).get("value", 0.3113113113113113))
        self.iou_nms = float(self.card_data.get("conf_threshold", {}).get("iou_nms", 0.6))
        self.imgsz = int(self.card_data.get("imgsz", 640))

        weights_path = settings.get_models_dir() / "weaveguard_yolo_v1" / "best.pt"
        self.model = YOLO(str(weights_path))
        self.is_loaded = True

    def infer(self, image: Image.Image) -> EngineResult:
        if not self.is_loaded or self.model is None:
            self.load()

        t_start = time.perf_counter()

        # 1. Prétraitement
        t_pre_0 = time.perf_counter()
        if image.mode != "RGB":
            image = image.convert("RGB")
        t_pre = (time.perf_counter() - t_pre_0) * 1000.0

        # 2. Inférence modèle
        t_mod_0 = time.perf_counter()
        results = self.model.predict(
            source=image,
            conf=self.conf,
            iou=self.iou_nms,
            imgsz=self.imgsz,
            verbose=False,
            device=self.device,
        )
        t_mod = (time.perf_counter() - t_mod_0) * 1000.0

        # 3. Post-traitement
        t_post_0 = time.perf_counter()
        boxes = results[0].boxes
        regions = []

        if boxes is not None and len(boxes) > 0:
            cls_ids = boxes.cls.cpu().numpy()
            confs = boxes.conf.cpu().numpy()
            xyxys = boxes.xyxy.cpu().numpy()

            # Tri par confiance décroissante
            order = confs.argsort()[::-1]
            for idx, i in enumerate(order):
                c = int(cls_ids[i])
                conf = float(confs[i])
                x0, y0, x1, y1 = map(float, xyxys[i])
                cls_name = self.classes[c] if c < len(self.classes) else f"Class_{c}"
                w = max(0.0, x1 - x0)
                h = max(0.0, y1 - y0)

                regions.append(
                    {
                        "region_id": f"Y{idx + 1}",
                        "source_engine": "yolo",
                        "bbox": [round(x0, 1), round(y0, 1), round(w, 1), round(h, 1)],
                        "area": round(w * h, 1),
                        "score": round(conf, 4),
                        "score_type": "confiance du modèle (non calibrée, pas une probabilité)",
                        "score_threshold": round(self.conf, 4),
                        "classification": cls_name,
                        "classification_method": "supervisé (YOLO)",
                        "label": f"Défaut proposé : {cls_name}",
                        "corroboration": None,
                    }
                )

        t_post = (time.perf_counter() - t_post_0) * 1000.0
        total_time = (time.perf_counter() - t_start) * 1000.0

        latency = LatencyBreakdown(
            preprocess_ms=round(t_pre, 2),
            model_ms=round(t_mod, 2),
            postprocess_ms=round(t_post, 2),
            total_ms=round(total_time, 2),
        )

        return EngineResult(
            engine_name="yolo",
            status="ok",
            regions=regions,
            raw_data={"n_detections": len(regions)},
            latency=latency,
        )

    def info(self) -> EngineInfo:
        if not self.card_data:
            card_path = settings.get_models_dir() / "weaveguard_yolo_v1" / "model_card.json"
            if card_path.exists():
                with open(card_path, "r", encoding="utf-8") as f:
                    self.card_data = json.load(f)

        return EngineInfo(
            engine_id="weaveguard_yolo_v1",
            version="v1",
            role="Détection supervisée de défauts textiles (classes connues uniquement)",
            artifacts_sha256={"best.pt": self.weights_sha256 or self.card_data.get("weights_sha256", "")},
            params={
                "imgsz": self.imgsz,
                "iou_nms": self.iou_nms,
                "base_model": self.card_data.get("base_model", "yolov8n.pt"),
            },
            thresholds={"conf": round(self.conf, 4)},
            labels={c: f"Défaut proposé : {c}" for c in self.classes},
        )

    def health(self) -> Dict[str, Any]:
        return {
            "name": "yolo",
            "is_loaded": self.is_loaded,
            "device": self.device,
            "classes_count": len(self.classes),
            "integrity_ok": bool(self.weights_sha256),
        }

    def unload(self) -> None:
        self.model = None
        self.is_loaded = False

