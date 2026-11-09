"""Moteur PatchCore pour la détection non supervisée d'anomalies (§5.2, AC-05, AC-06).

Ré-implémentation conforme aux notebooks 05 et 08 :
- Extracteur WideResNet50_2 (layers 2 + 3 avec pooling 3x3 et concaténation)
- Banque de mémoire de patches normaux (L2 NN par blocs bornés)
- Carte de distance interpolée avec flou gaussien sigma=4
- Libellé exact : « Anomalie suspectée — score de distance » (aucune classe, aucun pourcentage)
"""
import io
import json
import time
from typing import Any, Dict, List, Optional
import numpy as np
from PIL import Image
from scipy import ndimage
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models

from app.core.config import settings
from app.core.errors import ModelUnavailableException
from app.engines.base import BaseEngine, EngineInfo, EngineResult, LatencyBreakdown
from app.engines.integrity import IntegrityVerifier


class Extractor(nn.Module):
    def __init__(self, backbone_name: str = "wide_resnet50_2", feat_dim: int = 1024):
        super().__init__()
        m = getattr(torchvision.models, backbone_name)(weights="IMAGENET1K_V1")
        self.stem = nn.Sequential(m.conv1, m.bn1, m.relu, m.maxpool)
        self.l1 = m.layer1
        self.l2 = m.layer2
        self.l3 = m.layer3
        self.feat_dim = feat_dim
        for p in self.parameters():
            p.requires_grad = False

    @torch.inference_mode()
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        f2 = self.l2(self.l1(self.stem(x)))
        f3 = self.l3(f2)
        f2 = F.avg_pool2d(f2, 3, 1, 1)
        f3 = F.avg_pool2d(f3, 3, 1, 1)
        f3 = F.interpolate(f3, size=f2.shape[-2:], mode="bilinear", align_corners=False)
        f = torch.cat([f2, f3], dim=1)
        B, C, hh, ww = f.shape
        f = f.permute(0, 2, 3, 1).reshape(B * hh * ww, C)
        f = F.adaptive_avg_pool1d(f.unsqueeze(1), self.feat_dim).squeeze(1)
        return f.reshape(B, hh, ww, self.feat_dim)


class PatchCoreEngine(BaseEngine):
    def __init__(self):
        super().__init__(name="patchcore")
        self.device = torch.device(settings.get_effective_device())
        self.extractor: Optional[Extractor] = None
        self.bank: Optional[torch.Tensor] = None
        self.bank_squared_norm: Optional[torch.Tensor] = None
        self.scale: float = 0.5
        self.blur_sigma: float = 4.0
        self.feat_dim: int = 1024
        self.tau_global: float = 1.638649755716323
        self.min_region_area: int = 64
        self.memory_sha256: str = ""
        self.card_data: Dict[str, Any] = {}
        self.calibration_data: Dict[str, Any] = {}

        self.mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)

    def load(self) -> None:
        valid, exp_hash, act_hash = IntegrityVerifier.verify_patchcore_integrity()
        if not valid:
            raise ModelUnavailableException(
                message="Échec d'intégrité SHA-256 du modèle PatchCore (memory_bank.pt)",
                details={"expected": exp_hash, "actual": act_hash},
            )
        self.memory_sha256 = act_hash

        models_dir = settings.get_models_dir()
        pc_dir = models_dir / "patchcore" / "patchcore_v1"

        with open(pc_dir / "model_card.json", "r", encoding="utf-8") as f:
            self.card_data = json.load(f)

        with open(pc_dir / "calibration.json", "r", encoding="utf-8") as f:
            self.calibration_data = json.load(f)

        self.tau_global = float(self.calibration_data.get("tau_global", 1.638649755716323))
        self.min_region_area = int(self.calibration_data.get("min_region_area", 64))

        # Chargement de la banque de mémoire
        mb_file = pc_dir / "memory_bank.pt"
        mb_dict = torch.load(str(mb_file), weights_only=False, map_location="cpu")
        cfg = mb_dict.get("config", {})

        self.scale = float(cfg.get("scale", 0.5))
        self.blur_sigma = float(cfg.get("blur_sigma", 4.0))
        self.feat_dim = int(cfg.get("feature_dim", 1024))
        backbone_name = cfg.get("backbone", "wide_resnet50_2")

        # Chargement extracteur
        self.extractor = Extractor(backbone_name=backbone_name, feat_dim=self.feat_dim).to(self.device).eval()

        # Banque chargée sur le device
        # Sur CPU, le calcul tensoriel L2 s'exécute en float32
        self.bank = mb_dict["bank"].float().to(self.device)
        self.bank_squared_norm = (self.bank ** 2).sum(dim=1)

        self.mean = self.mean.to(self.device)
        self.std = self.std.to(self.device)

        self.is_loaded = True

    @torch.inference_mode()
    def _nn_dist(self, Q: torch.Tensor, chunk: int = 4096) -> torch.Tensor:
        """Distance L2 au plus proche patch de la banque par blocs avec mémoire bornée."""
        bn = self.bank_squared_norm
        out = torch.empty(Q.shape[0], device=self.device)
        for i in range(0, Q.shape[0], chunk):
            q = Q[i : i + chunk].float()
            d2 = (q ** 2).sum(dim=1, keepdim=True) - 2 * q @ self.bank.T + bn[None]
            out[i : i + chunk] = d2.min(dim=1).values.clamp_min(0).sqrt()
        return out

    def infer(self, image: Image.Image) -> EngineResult:
        if not self.is_loaded or self.extractor is None or self.bank is None:
            self.load()

        t_start = time.perf_counter()

        # 1. Prétraitement
        t_pre_0 = time.perf_counter()
        if image.mode != "RGB":
            image = image.convert("RGB")
        W_orig, H_orig = image.size
        W_sc, H_sc = round(W_orig * self.scale), round(H_orig * self.scale)
        im_resized = image.resize((W_sc, H_sc), Image.BILINEAR)

        x_np = np.asarray(im_resized, dtype=np.float32) / 255.0
        x_tensor = torch.from_numpy(x_np).permute(2, 0, 1).to(self.device)
        x_norm = (x_tensor - self.mean) / self.std
        t_pre = (time.perf_counter() - t_pre_0) * 1000.0

        # 2. Modèle (Extraction + Distance NN)
        t_mod_0 = time.perf_counter()
        with torch.inference_mode():
            feats = self.extractor(x_norm[None])  # shape: (1, hh, ww, feat_dim)
            _, hh, ww, d = feats.shape

            dist = self._nn_dist(feats.reshape(-1, d), chunk=4096).reshape(1, 1, hh, ww)
            raw_map = F.interpolate(dist, size=(H_sc, W_sc), mode="bilinear", align_corners=False)[0, 0].cpu().numpy()
        t_mod = (time.perf_counter() - t_mod_0) * 1000.0

        # 3. Post-traitement (Flou Gaussien + Composantes connexes)
        t_post_0 = time.perf_counter()
        score_map = ndimage.gaussian_filter(raw_map, sigma=self.blur_sigma)
        score_global = float(score_map.max())

        # Détection des composantes connexes à tau_global
        labeled, _ = ndimage.label(score_map >= self.tau_global)
        objects = ndimage.find_objects(labeled)

        regions = []
        factor = 1.0 / self.scale

        if objects:
            temp_regions = []
            for k, sl in enumerate(objects, 1):
                if sl is None:
                    continue
                mask = labeled[sl] == k
                area_sc = int(mask.sum())
                if area_sc < self.min_region_area:
                    continue

                v = score_map[sl][mask]
                s_max = float(v.max())
                s_mean = float(v.mean())

                x0_sc, y0_sc = sl[1].start, sl[0].start
                x1_sc, y1_sc = sl[1].stop, sl[0].stop

                temp_regions.append(
                    {
                        "x0": x0_sc * factor,
                        "y0": y0_sc * factor,
                        "x1": x1_sc * factor,
                        "y1": y1_sc * factor,
                        "area_px": area_sc,
                        "score_max": s_max,
                        "score_mean": s_mean,
                    }
                )

            # Tri par score max décroissant
            temp_regions.sort(key=lambda r: r["score_max"], reverse=True)

            for idx, r in enumerate(temp_regions):
                x0, y0, x1, y1 = r["x0"], r["y0"], r["x1"], r["y1"]
                w = max(0.0, x1 - x0)
                h = max(0.0, y1 - y0)
                regions.append(
                    {
                        "region_id": f"P{idx + 1}",
                        "source_engine": "patchcore",
                        "bbox": [round(x0, 1), round(y0, 1), round(w, 1), round(h, 1)],
                        "area": round(w * h, 1),
                        "score": round(r["score_max"], 3),
                        "score_type": f"distance L2 (brut, seuil {self.tau_global:.3f})",
                        "score_threshold": round(self.tau_global, 3),
                        "classification": None,
                        "classification_method": None,
                        "label": "Anomalie suspectée — score de distance",
                        "corroboration": None,
                        "score_mean": round(r["score_mean"], 3),
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

        min_val = float(score_map.min())
        max_val = float(score_map.max())

        return EngineResult(
            engine_name="patchcore",
            status="ok",
            regions=regions,
            raw_data={
                "score_global": round(score_global, 4),
                "map_shape": list(score_map.shape),
                "map_min": round(min_val, 4),
                "map_max": round(max_val, 4),
                "tau_global": round(self.tau_global, 4),
                "score_map": score_map,  # Conservé pour la génération de heatmap.png
                "heatmap_meta": {
                    "scale": "raw",
                    "min": round(min_val, 4),
                    "max": round(max_val, 4),
                    "tau": round(self.tau_global, 4),
                },
            },
            latency=latency,
        )

    def info(self) -> EngineInfo:
        return EngineInfo(
            engine_id="patchcore_v1",
            version="v1",
            role="Détection d anomalies : anomalie suspectée + score de distance (pas de classe, pas de probabilité)",
            artifacts_sha256={"memory_bank.pt": self.memory_sha256},
            params={
                "backbone": "wide_resnet50_2",
                "scale": self.scale,
                "blur_sigma": self.blur_sigma,
                "feature_dim": self.feat_dim,
                "distance": "L2",
            },
            thresholds={
                "tau_global": round(self.tau_global, 4),
                "min_region_area": self.min_region_area,
            },
            labels={"region": "Anomalie suspectée — score de distance"},
        )

    def health(self) -> Dict[str, Any]:
        return {
            "name": "patchcore",
            "is_loaded": self.is_loaded,
            "device": str(self.device),
            "bank_patches": self.bank.shape[0] if self.bank is not None else 0,
            "tau_global": self.tau_global,
            "integrity_ok": bool(self.memory_sha256),
        }

    def unload(self) -> None:
        self.extractor = None
        self.bank = None
        self.bank_squared_norm = None
        self.is_loaded = False
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

