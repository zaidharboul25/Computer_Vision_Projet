"""Moteur de similarité visuelle (ResNet-50 + FAISS) (§5.3, AC-05, AC-06).

Recherche de textiles similaires dans la galerie WeaveGuard v2 et
de textures similaires dans la galerie générique DTD.
Libellés contractuels stricts :
- Index WeaveGuard : « Textiles similaires (index WeaveGuard) »
- Index DTD        : « Textures similaires (galerie DTD générique) »
"""
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import faiss
import numpy as np
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models
import torchvision.transforms as T

from app.core.config import settings
from app.core.errors import ModelUnavailableException
from app.engines.base import BaseEngine, EngineInfo, EngineResult, LatencyBreakdown
from app.engines.integrity import IntegrityVerifier


class Embedder(nn.Module):
    def __init__(self):
        super().__init__()
        m = torchvision.models.resnet50(weights="IMAGENET1K_V1")
        self.body = nn.Sequential(
            m.conv1, m.bn1, m.relu, m.maxpool, m.layer1, m.layer2, m.layer3, m.layer4
        )
        for p in self.parameters():
            p.requires_grad = False

    @torch.inference_mode()
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Global Average Pooling sur layer4 -> 2048, puis normalisation L2
        pooled = self.body(x).mean(dim=(2, 3))
        return F.normalize(pooled, dim=1)


class SimilarityEngine(BaseEngine):
    def __init__(self):
        super().__init__(name="similarity")
        self.device = torch.device(settings.get_effective_device())
        self.embedder: Optional[Embedder] = None
        self.idx_dtd: Optional[faiss.IndexFlatIP] = None
        self.idx_wg: Optional[faiss.IndexFlatIP] = None
        self.meta_dtd: List[Dict[str, Any]] = []
        self.meta_wg: List[Dict[str, Any]] = []
        self.config_data: Dict[str, Any] = {}
        self.artifacts_sha256: Dict[str, str] = {}

        # Prétraitement strict du notebook 06 : Resize(256) plus petit côté + CenterCrop(256)
        self.transform = T.Compose(
            [
                T.Resize(256),
                T.CenterCrop(256),
                T.ToTensor(),
                T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )

    def load(self) -> None:
        integrity_results = IntegrityVerifier.verify_similarity_integrity()
        for filename, (valid, exp_hash, act_hash) in integrity_results.items():
            if not valid:
                raise ModelUnavailableException(
                    message=f"Échec d'intégrité SHA-256 pour l'artefact de similarité '{filename}'",
                    details={"artifact": filename, "expected": exp_hash, "actual": act_hash},
                )
            self.artifacts_sha256[filename] = act_hash

        models_dir = settings.get_models_dir()
        sim_dir = models_dir / "similarity" / "similarity_v1"

        with open(sim_dir / "config.json", "r", encoding="utf-8") as f:
            self.config_data = json.load(f)

        with open(sim_dir / "metadata_dtd.json", "r", encoding="utf-8") as f:
            self.meta_dtd = json.load(f)

        with open(sim_dir / "metadata_weaveguard.json", "r", encoding="utf-8") as f:
            self.meta_wg = json.load(f)

        self.idx_dtd = faiss.read_index(str(sim_dir / "index_dtd.faiss"))
        self.idx_wg = faiss.read_index(str(sim_dir / "index_weaveguard.faiss"))

        self.embedder = Embedder().to(self.device).eval()
        self.is_loaded = True

    def search(
        self,
        image: Image.Image,
        index_name: str = "weaveguard",
        k: int = 5,
    ) -> Dict[str, Any]:
        """Recherche les k plus proches voisins dans l'index sélectionné."""
        if not self.is_loaded or self.embedder is None:
            self.load()

        if index_name not in ("weaveguard", "dtd"):
            raise ValueError(f"Index de similarité inconnu : '{index_name}' (choix: weaveguard, dtd)")

        t_pre_0 = time.perf_counter()
        if image.mode != "RGB":
            image = image.convert("RGB")
        x_tensor = self.transform(image).unsqueeze(0).to(self.device)
        t_pre = (time.perf_counter() - t_pre_0) * 1000.0

        t_mod_0 = time.perf_counter()
        with torch.inference_mode():
            feat = self.embedder(x_tensor).cpu().numpy().astype(np.float32)
        t_mod = (time.perf_counter() - t_mod_0) * 1000.0

        t_post_0 = time.perf_counter()
        if index_name == "weaveguard":
            idx = self.idx_wg
            meta = self.meta_wg
            allowed = self.config_data.get("allowed_fields", {}).get("weaveguard", ["ref_id", "source", "classes", "split"])
            ui_label = "Textiles similaires (index WeaveGuard)"
        else:
            idx = self.idx_dtd
            meta = self.meta_dtd
            allowed = self.config_data.get("allowed_fields", {}).get("dtd", ["ref_id", "source", "category"])
            ui_label = "Textures similaires (galerie DTD générique)"

        k = max(1, min(k, idx.ntotal))
        distances, indices = idx.search(feat, k)

        results = []
        for r in range(k):
            item_idx = int(indices[0, r])
            score_cos = float(distances[0, r])
            item_meta = meta[item_idx]

            # Filtrage strict : seuls les champs autorisés sont renvoyés (jamais de chemin local)
            filtered_item = {f: item_meta[f] for f in allowed if f in item_meta}
            filtered_item["rank"] = r + 1
            filtered_item["score"] = round(score_cos, 4)
            results.append(filtered_item)

        t_post = (time.perf_counter() - t_post_0) * 1000.0

        return {
            "engine": "similarity",
            "extractor": self.config_data.get("extractor_id", "resnet50_imagenet1k_v1_gap2048_l2"),
            "index": index_name,
            "metric": "cosine_similarity",
            "higher_is_better": True,
            "label": ui_label,
            "note": "similarité visuelle ; ce n est pas une détection de défaut",
            "latency_ms": {
                "preprocess": round(t_pre, 2),
                "model": round(t_mod, 2),
                "search": round(t_post, 2),
                "total": round(t_pre + t_mod + t_post, 2),
            },
            "results": results,
        }

    def infer(self, image: Image.Image) -> EngineResult:
        """Exécution par défaut de la similarité sur les deux index pour le pipeline d'inspection."""
        t_0 = time.perf_counter()
        wg_res = self.search(image, index_name="weaveguard", k=5)
        dtd_res = self.search(image, index_name="dtd", k=5)
        total_time = (time.perf_counter() - t_0) * 1000.0

        latency = LatencyBreakdown(
            preprocess_ms=wg_res["latency_ms"]["preprocess"],
            model_ms=wg_res["latency_ms"]["model"] + dtd_res["latency_ms"]["model"],
            postprocess_ms=wg_res["latency_ms"]["search"] + dtd_res["latency_ms"]["search"],
            total_ms=round(total_time, 2),
        )

        return EngineResult(
            engine_name="similarity",
            status="ok",
            regions=[],  # La similarité ne produit aucune boîte de défaut
            raw_data={
                "weaveguard": wg_res,
                "dtd": dtd_res,
            },
            latency=latency,
        )

    def resolve_ref_thumbnail(self, ref_id: str) -> Path:
        """Résout de manière sûre le chemin d'image associé à un ref_id (anti path-traversal)."""
        if not ref_id or ".." in ref_id:
            raise ValueError("Identifiant de référence invalide")

        if ref_id.startswith("dtd:"):
            rel = ref_id[4:].strip().replace("\\", "/")
            path = (settings.get_dtd_dir() / rel).resolve()
            # Anti-traversal : le chemin doit être strictement sous DTD_DIR
            if not path.is_relative_to(settings.get_dtd_dir()) or not path.exists():
                raise FileNotFoundError(f"Référence DTD introuvable : {ref_id}")
            return path

        if ref_id.startswith("weaveguard-v2:"):
            name = ref_id[14:].strip()
            # Recherche dans train, val (jamais test)
            dataset_dir = settings.get_dataset_dir() / "images"
            for split in ("train", "val"):
                candidate = (dataset_dir / split / name).resolve()
                if candidate.exists() and candidate.is_relative_to(dataset_dir):
                    return candidate
            raise FileNotFoundError(f"Référence WeaveGuard introuvable : {ref_id}")

        raise ValueError(f"Schéma de référence non reconnu : {ref_id}")

    def info(self) -> EngineInfo:
        return EngineInfo(
            engine_id="similarity_v1",
            version="v1",
            role="Recherche de textiles similaires (similarité visuelle, pas une détection de défaut)",
            artifacts_sha256=self.artifacts_sha256,
            params={
                "backbone": "resnet50",
                "dim": 2048,
                "metric": "cosine_similarity",
                "index_type": "IndexFlatIP",
            },
            thresholds={},
            labels={
                "weaveguard": "Textiles similaires (index WeaveGuard)",
                "dtd": "Textures similaires (galerie DTD générique)",
            },
        )

    def health(self) -> Dict[str, Any]:
        return {
            "name": "similarity",
            "is_loaded": self.is_loaded,
            "device": str(self.device),
            "ntotal_dtd": self.idx_dtd.ntotal if self.idx_dtd is not None else 0,
            "ntotal_weaveguard": self.idx_wg.ntotal if self.idx_wg is not None else 0,
            "integrity_ok": len(self.artifacts_sha256) > 0,
        }

    def unload(self) -> None:
        self.embedder = None
        self.idx_dtd = None
        self.idx_wg = None
        self.is_loaded = False
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

