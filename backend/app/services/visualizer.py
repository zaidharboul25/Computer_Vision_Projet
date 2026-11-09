"""Génération des visualisations : Heatmap normalisée et Overlay annoté (Phase 3).

Respecte rigoureusement :
- AC-03 : L'overlay téléchargé correspond exactement aux résultats affichés / stockés dans la base.
- Exigence F : Heatmap PNG 8 bits avec normalisation documentée (0 -> 0, vmax -> 255) et métadonnées associées.
"""
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from app.schemas.inspection import HeatmapMeta

# Emplacement de la police TrueType embarquée pour le rendu multilingue / caractères accentués
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
DEJAVU_FONT_PATH = FONT_DIR / "DejaVuSans.ttf"


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    p0: Tuple[int, int],
    p1: Tuple[int, int],
    color: Tuple[int, int, int],
    width: int,
    dash_len: int,
    gap_len: int,
) -> None:
    """Trace un segment pointillé/tireté entre p0 et p1."""
    x0, y0 = p0
    x1, y1 = p1
    dx = x1 - x0
    dy = y1 - y0
    distance = (dx**2 + dy**2) ** 0.5
    if distance <= 0:
        return
    ux = dx / distance
    uy = dy / distance
    curr = 0.0
    while curr < distance:
        end = min(curr + dash_len, distance)
        draw.line(
            [
                (int(round(x0 + curr * ux)), int(round(y0 + curr * uy))),
                (int(round(x0 + end * ux)), int(round(y0 + end * uy))),
            ],
            fill=color,
            width=width,
        )
        curr += dash_len + gap_len


def _draw_dashed_rect(
    draw: ImageDraw.ImageDraw,
    rect: Tuple[int, int, int, int],
    color: Tuple[int, int, int],
    width: int,
) -> None:
    """Trace un rectangle aux arêtes pointillées (spécifique PatchCore)."""
    x0, y0, x1, y1 = rect
    dash_len = max(5, width * 3)
    gap_len = max(3, width * 2)
    _draw_dashed_line(draw, (x0, y0), (x1, y0), color, width, dash_len, gap_len)
    _draw_dashed_line(draw, (x1, y0), (x1, y1), color, width, dash_len, gap_len)
    _draw_dashed_line(draw, (x1, y1), (x0, y1), color, width, dash_len, gap_len)
    _draw_dashed_line(draw, (x0, y1), (x0, y0), color, width, dash_len, gap_len)


class VisualizerService:
    @staticmethod
    def generate_heatmap(
        raw_score_map: np.ndarray,
        stored_size: Tuple[int, int],  # (width, height)
        tau: float,
    ) -> Tuple[Image.Image, HeatmapMeta]:
        """Génère la heatmap PNG 8 bits normalisée et ses métadonnées.

        Formule de normalisation documentée :
        vmax = max(raw_score_map) si max > 0 sinon 1.0
        norm_map = clip((raw_score_map / vmax) * 255, 0, 255) (uint8)
        """
        stored_w, stored_h = stored_size
        min_val = float(np.min(raw_score_map))
        max_val = float(np.max(raw_score_map))
        vmax = max(2.0 * float(tau), max_val)
        if vmax <= 0.0:
            vmax = 1.0

        # Normalisation 0 -> 0, vmax -> 255
        norm_arr = np.clip((raw_score_map / vmax) * 255.0, 0, 255).astype(np.uint8)

        # Redimensionnement de la carte pour épouser exactement les dimensions de l'image stockée
        heatmap_img = Image.fromarray(norm_arr, mode="L")
        if (heatmap_img.width, heatmap_img.height) != (stored_w, stored_h):
            heatmap_img = heatmap_img.resize((stored_w, stored_h), Image.Resampling.BILINEAR)

        meta = HeatmapMeta(
            scale="raw",
            min=round(min_val, 4),
            max=round(max_val, 4),
            tau=round(tau, 4),
            vmax=round(vmax, 4),
            width=stored_w,
            height=stored_h,
        )

        return heatmap_img, meta

    @staticmethod
    def generate_overlay(
        stored_image: Image.Image,
        regions: List[Dict],
    ) -> Image.Image:
        """Génère l'image d'overlay avec boîtes, badges courts à l'intérieur et bandeau de légende sous l'image (AC-03).

        Règles d'ergonomie et d'accessibilité visuelle :
        - Sur l'image : SEULEMENT un badge court 'Y1', 'P1'... posé à l'INTÉRIEUR de l'image (jamais coupé).
        - YOLO : trait plein + lettre 'Y'.
        - PatchCore : trait POINTILLÉ (tirets explicites) + lettre 'P'.
        - La couleur seule ne porte jamais le sens.
        - Épaisseur et police proportionnelles à la largeur d'image.
        - Texte complet placé dans un bandeau de légende ajouté sous l'image (une ligne par région).
        """
        img_w, img_h = stored_image.size
        overlay = stored_image.copy().convert("RGB")
        draw = ImageDraw.Draw(overlay)

        # Couleurs déterministes par moteur / corroboration
        COLOR_YOLO = (255, 87, 34)         # Orange vif (YOLO)
        COLOR_PATCHCORE = (3, 169, 244)     # Bleu cyan (PatchCore)
        COLOR_CORROBORATED = (233, 30, 99)  # Magenta profond (Corroboration)

        # Dimensionnement proportionnel dynamique
        line_width = max(2, int(round(img_w * 0.003)))
        badge_font_size = max(11, int(round(img_w * 0.016)))
        legend_font_size = max(11, int(round(img_w * 0.015)))

        badge_font = None
        legend_font = None
        if DEJAVU_FONT_PATH.exists():
            try:
                badge_font = ImageFont.truetype(str(DEJAVU_FONT_PATH), size=badge_font_size)
                legend_font = ImageFont.truetype(str(DEJAVU_FONT_PATH), size=legend_font_size)
            except Exception:
                pass

        if badge_font is None:
            try:
                badge_font = ImageFont.load_default()
                legend_font = ImageFont.load_default()
            except Exception:
                pass

        # 1. Tracé des boîtes et des badges courts sur l'image
        for idx, reg in enumerate(regions):
            bbox = reg.get("bbox", [0, 0, 0, 0])
            x, y, w, h = bbox
            engine = reg.get("engine", "yolo")
            corroboration = reg.get("corroboration") or {}
            is_corroborated = corroboration.get("detected", False)

            if is_corroborated:
                color = COLOR_CORROBORATED
            elif engine == "yolo":
                color = COLOR_YOLO
            else:
                color = COLOR_PATCHCORE

            # Clamping des coordonnées dans le repère de l'image
            x0 = max(0, min(img_w - 1, int(round(x))))
            y0 = max(0, min(img_h - 1, int(round(y))))
            x1 = max(0, min(img_w - 1, int(round(x + w))))
            y1 = max(0, min(img_h - 1, int(round(y + h))))

            # Style de tracé : YOLO = trait plein, PatchCore = trait pointillé
            if engine == "yolo":
                draw.rectangle([x0, y0, x1, y1], outline=color, width=line_width)
            else:
                _draw_dashed_rect(draw, (x0, y0, x1, y1), color=color, width=line_width)

            # Badge court d'affichage : Y1, Y2... ou P1, P2...
            disp_id = reg.get("display_id")
            if not disp_id:
                disp_id = f"Y{idx+1}" if engine == "yolo" else f"P{idx+1}"
            badge_text = disp_id

            # Mesure du badge
            if badge_font:
                bbox_t = draw.textbbox((0, 0), badge_text, font=badge_font)
                bw = (bbox_t[2] - bbox_t[0]) + 8
                bh = (bbox_t[3] - bbox_t[1]) + 6
            else:
                bw = len(badge_text) * 8 + 8
                bh = 16

            # Positionnement du badge à l'INTÉRIEUR de l'image (jamais coupé)
            # Cible idéale : coin supérieur gauche de la boîte
            bx = x0 + line_width + 1
            by = y0 + line_width + 1

            # Recalage strict vers l'intérieur pour éviter tout dépassement
            bx = max(2, min(bx, img_w - bw - 2))
            by = max(2, min(by, img_h - bh - 2))

            # Fond semi-opaque derrière le badge
            badge_layer = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
            b_draw = ImageDraw.Draw(badge_layer)
            b_draw.rectangle([bx, by, bx + bw, by + bh], fill=(15, 23, 42, 220), outline=color, width=1)
            overlay = Image.alpha_composite(overlay.convert("RGBA"), badge_layer).convert("RGB")
            draw = ImageDraw.Draw(overlay)

            # Dessin du badge textuel
            if badge_font:
                draw.text((bx + 4, by + 3), badge_text, fill=(255, 255, 255), font=badge_font)
            else:
                draw.text((bx + 4, by + 3), badge_text, fill=(255, 255, 255))

        # 2. Bandeau de légende ajouté SOUS l'image (pas posé sur le tissu)
        line_height = max(18, int(round(legend_font_size * 1.6)))
        header_height = max(22, int(round(legend_font_size * 1.8)))
        padding_y = 12

        num_lines = len(regions) if len(regions) > 0 else 1
        banner_height = header_height + num_lines * line_height + padding_y

        full_img = Image.new("RGB", (img_w, img_h + banner_height), color=(15, 23, 42))  # Fond sombre Slate 900
        full_img.paste(overlay, (0, 0))

        leg_draw = ImageDraw.Draw(full_img)
        # Ligne de séparation fine sous le tissu
        leg_draw.line([(0, img_h), (img_w, img_h)], fill=(51, 65, 85), width=2)

        # En-tête de légende
        leg_draw.text(
            (10, img_h + 6),
            "LÉGENDE DES DÉTECTIONS :",
            fill=(203, 213, 225),
            font=legend_font,
        )

        if len(regions) == 0:
            leg_draw.text(
                (10, img_h + header_height + 4),
                "Aucune région détectée par les moteurs exécutés (ce résultat n'est pas une garantie d'absence de défaut)",
                fill=(148, 163, 184),
                font=legend_font,
            )
        else:
            for idx, reg in enumerate(regions):
                engine = reg.get("engine", "yolo")
                disp_id = reg.get("display_id") or (f"Y{idx+1}" if engine == "yolo" else f"P{idx+1}")
                label = reg.get("label", "")
                score = reg.get("score")
                corro = reg.get("corroboration") or {}

                if engine == "yolo":
                    score_txt = f" | Confiance : {score:.2f}" if score is not None else ""
                    corro_txt = ""
                    if corro.get("detected"):
                        pc_s = corro.get("score_patchcore")
                        corro_txt = f" [Corroboré PatchCore distance: {pc_s:.4f}]" if pc_s is not None else " [Corroboré PatchCore]"
                    line_txt = f"[{disp_id}] [YOLO • Trait plein] {label}{score_txt}{corro_txt}"
                    text_color = (253, 186, 116) if not corro.get("detected") else (244, 114, 182)
                else:
                    score_txt = f" : {score:.4f}" if score is not None else ""
                    tau = reg.get("tau")
                    tau_txt = f" (seuil τ: {tau:.4f})" if tau is not None else ""
                    line_txt = f"[{disp_id}] [PatchCore • Trait pointillé] {label}{score_txt}{tau_txt}"
                    text_color = (125, 211, 252)

                y_pos = img_h + header_height + idx * line_height
                leg_draw.text((10, y_pos), line_txt, fill=text_color, font=legend_font)

        return full_img

