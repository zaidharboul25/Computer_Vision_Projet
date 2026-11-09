"""Algorithme de fusion YOLO + PatchCore (§5.4, AC-05, AC-06, fusion_spec.json).

Spécifications contractuelles :
- Conserve toutes les détections YOLO (classe et score intacts)
- Rattache les régions PatchCore en corroboration si recouvrement >= 10 % de la boîte OU >= 50 % de la région
- Région PatchCore orpheline conservée comme anomalie distincte (sans classe)
- La corroboration est une aide à la priorisation, jamais un filtre automatique
"""
from typing import Any, Dict, List, Optional, Tuple


def _inter(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def _area(b: Tuple[float, float, float, float]) -> float:
    return max(1e-9, (b[2] - b[0]) * (b[3] - b[1]))


def check_overlap(
    yolo_box_xyxy: Tuple[float, float, float, float],
    patchcore_box_xyxy: Tuple[float, float, float, float],
) -> bool:
    """Règle de recouvrement : >= 10 % de la boîte YOLO OU >= 50 % de la région PatchCore."""
    i = _inter(yolo_box_xyxy, patchcore_box_xyxy)
    return (i / _area(yolo_box_xyxy) >= 0.10) or (i / _area(patchcore_box_xyxy) >= 0.50)


def fuse_regions(
    yolo_regions: List[Dict[str, Any]],
    patchcore_regions: List[Dict[str, Any]],
    tau: float = 1.638649755716323,
) -> List[Dict[str, Any]]:
    """Fusionne les détections YOLO et les anomalies PatchCore selon fusion_spec.json."""
    fused: List[Dict[str, Any]] = []

    # 1. Conversion des coordonnées PatchCore en xyxy pour les calculs d'intersection
    pcr_boxes = []
    for r in patchcore_regions:
        x, y, w, h = r["bbox"]
        pcr_boxes.append((x, y, x + w, y + h, r))

    # 2. Traitement des détections YOLO (triées par score décroissant)
    sorted_yolo = sorted(yolo_regions, key=lambda d: d.get("score", 0.0), reverse=True)
    matched_pcr_indices = set()

    for idx, y_det in enumerate(sorted_yolo):
        yx, yy, yw, yh = y_det["bbox"]
        y_box = (yx, yy, yx + yw, yy + yh)

        # Recherche de toutes les régions PatchCore qui recouvrent cette détection YOLO
        overlapping_pcr = []
        for p_idx, (px0, py0, px1, py1, p_dict) in enumerate(pcr_boxes):
            if check_overlap(y_box, (px0, py0, px1, py1)):
                overlapping_pcr.append(p_dict)
                matched_pcr_indices.add(p_idx)

        # Corroboration si au moins une région PatchCore recouvre
        if overlapping_pcr:
            max_corro_score = max(r.get("score", 0.0) for r in overlapping_pcr)
            corroboration = {
                "engine": "patchcore",
                "score": round(max_corro_score, 3),
                "threshold": round(tau, 3),
            }
        else:
            corroboration = None

        fused_item = dict(y_det)
        fused_item["region_id"] = f"Y{idx + 1}"
        fused_item["corroboration"] = corroboration
        fused.append(fused_item)

    # 3. Traitement des régions PatchCore orphelines (sans aucun équivalent YOLO)
    orphaned_pcr = [
        pcr_boxes[i][4]
        for i in range(len(pcr_boxes))
        if i not in matched_pcr_indices
    ]
    # Tri des orphelines par score décroissant
    orphaned_pcr.sort(key=lambda d: d.get("score", 0.0), reverse=True)

    for idx, p_det in enumerate(orphaned_pcr):
        fused_p = dict(p_det)
        fused_p["region_id"] = f"P{idx + 1}"
        fused_p["classification"] = None
        fused_p["classification_method"] = None
        fused_p["label"] = "Anomalie suspectée — score de distance"
        fused_p["corroboration"] = None
        fused.append(fused_p)

    return fused

