"""Service de stockage et de prétraitement des images d'inspection (Phase 3).

Assure :
- La validation stricte des uploads (taille max, format JPEG/PNG, garde anti-bombe de décompression,
  rejet des GIFs animés et des fichiers corrompus ou vides).
- La conversion propre en RGB 8-bit (niveaux de gris, RGBA, 16-bit).
- Le redressement selon l'orientation EXIF (AC-02).
- Le redimensionnement proportionnel si max(côté) > INFERENCE_LONG_SIDE.
- La projection exacte des coordonnées entre repère d'inférence et repère de l'image stockée.
- L'isolation stricte des chemins de stockage (aucun nom de fichier externe utilisé comme chemin).
"""
import io
import re
from pathlib import Path
from typing import List, Tuple
import numpy as np
from PIL import Image, ImageOps
from app.core.config import settings
from app.core.errors import FileTooLargeException, ImageTooLargeException, InvalidImageException
from app.schemas.inspection import ImageMeta


# Configuration de la garde anti-bombe de décompression
MAX_PIXELS_LIMIT = settings.MAX_IMAGE_SIDE * settings.MAX_IMAGE_SIDE
Image.MAX_IMAGE_PIXELS = MAX_PIXELS_LIMIT


class StorageService:
    @staticmethod
    def get_inspection_dir(inspection_id: str) -> Path:
        """Renvoie le dossier sécurisé d'une inspection, créé s'il n'existe pas."""
        # Validation stricte du format UUID pour bannir tout path traversal
        if not re.match(r"^[a-fA-F0-9\-]{36}$", inspection_id):
            raise ValueError(f"Identifiant d'inspection non conforme : {inspection_id}")
        folder = settings.get_storage_dir() / "inspections" / inspection_id
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    @staticmethod
    def validate_and_preprocess_upload(
        file_bytes: bytes, original_filename: str, scale_mode: str = "native"
    ) -> Tuple[Image.Image, Image.Image, ImageMeta]:
        """Valide l'image soumise, extrait l'orientation EXIF, convertit en RGB et génère l'image d'inférence.

        Returns:
            (stored_image, inference_image, image_meta)
        """
        # 1. Vérification de fichier vide
        if not file_bytes or len(file_bytes) == 0:
            raise InvalidImageException("Le fichier image téléchargé est vide", details={"reason": "empty_file"})

        # 2. Vérification de la taille en Mo
        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ImageTooLargeException(
                f"La taille du fichier ({len(file_bytes)} octets) dépasse la limite autorisée de {settings.MAX_UPLOAD_MB} Mo"
            )

        # 3. Ouverture et vérification anti-bombe / corruption
        try:
            raw_img = Image.open(io.BytesIO(file_bytes))
            raw_img.load()
        except Image.DecompressionBombError:
            raise ImageTooLargeException("Les dimensions de l'image dépassent la limite de sécurité anti-décompression")
        except Exception as e:
            raise InvalidImageException(f"Fichier image invalide ou corrompu : {str(e)}")

        # 4. Rejet des GIFs et images animées
        if raw_img.format == "GIF" or getattr(raw_img, "is_animated", False):
            raise InvalidImageException("Les formats GIF et images animées ne sont pas autorisés")

        # 5. Formats autorisés (JPEG, PNG)
        detected_format = (raw_img.format or "").upper()
        if detected_format not in ["JPEG", "PNG", "JPG", "MPO"]:
            raise InvalidImageException(
                f"Format {detected_format or 'inconnu'} non supporté. Formats acceptés : JPEG, PNG"
            )

        orig_w, orig_h = raw_img.size
        if orig_w > settings.MAX_IMAGE_SIDE or orig_h > settings.MAX_IMAGE_SIDE:
            raise ImageTooLargeException(
                f"Dimensions de l'image ({orig_w}x{orig_h}) supérieures au maximum autorisé ({settings.MAX_IMAGE_SIDE})"
            )

        warnings: List[str] = []

        # 6. Conversion en RGB documentée
        if raw_img.mode != "RGB":
            warnings.append(f"Mode de couleur converti de {raw_img.mode} en RGB 8-bit")
            if raw_img.mode in ("RGBA", "LA"):
                # Fond blanc neutre pour la transparence
                background = Image.new("RGB", raw_img.size, (255, 255, 255))
                background.paste(raw_img, mask=raw_img.split()[-1])
                img_rgb = background
            elif raw_img.mode.startswith("I"):
                # Image 16/32 bits : normalisation sur 8 bits
                arr = np.array(raw_img)
                norm = ((arr - arr.min()) / max(1, (arr.max() - arr.min())) * 255.0).astype(np.uint8)
                img_rgb = Image.fromarray(norm).convert("RGB")
            else:
                img_rgb = raw_img.convert("RGB")
        else:
            img_rgb = raw_img

        # 7. Redressement EXIF (AC-02)
        oriented_img = ImageOps.exif_transpose(img_rgb)
        stored_w, stored_h = oriented_img.size
        if (stored_w, stored_h) != (orig_w, orig_h):
            warnings.append(f"Redressement EXIF appliqué : dimensions {orig_w}x{orig_h} -> {stored_w}x{stored_h}")

        # 8. Redimensionnement pour l'inférence
        max_side = max(stored_w, stored_h)
        if max_side > settings.INFERENCE_LONG_SIDE:
            scale = settings.INFERENCE_LONG_SIDE / float(max_side)
            inf_w = max(1, int(round(stored_w * scale)))
            inf_h = max(1, int(round(stored_h * scale)))
            inf_img = oriented_img.resize((inf_w, inf_h), Image.Resampling.BILINEAR)
            warnings.append(
                f"Image redimensionnée pour l'inférence : échelle {scale:.4f} ({stored_w}x{stored_h} -> {inf_w}x{inf_h})"
            )
        else:
            if scale_mode == "normalized" and max_side < settings.INFERENCE_LONG_SIDE:
                # Mode expérimental 'normalized' : agrandissement bicubique jusqu'à INFERENCE_LONG_SIDE
                scale = settings.INFERENCE_LONG_SIDE / float(max_side)
                inf_w = max(1, int(round(stored_w * scale)))
                inf_h = max(1, int(round(stored_h * scale)))
                inf_img = oriented_img.resize((inf_w, inf_h), Image.Resampling.BICUBIC)
                warnings.append("image agrandie : l'agrandissement n'ajoute pas d'information")
            else:
                scale = 1.0
                inf_w = stored_w
                inf_h = stored_h
                inf_img = oriented_img

            # Avertissement d'échelle explicite si l'image est nettement plus petite que la référence d'inférence
            if max_side < settings.INFERENCE_LONG_SIDE:
                factor = round(max_side / float(settings.INFERENCE_LONG_SIDE), 4)
                warnings.append(
                    f"Image de petite taille par rapport à la référence d'inférence ({stored_w}x{stored_h} vs {settings.INFERENCE_LONG_SIDE} px, facteur {factor:.2f})."
                )

        # Assainissement du nom de fichier original (aucun caractère de séparation de chemin)
        clean_filename = Path(original_filename).name or "upload.png"
        clean_filename = re.sub(r"[^\w\.\-]", "_", clean_filename)

        image_meta = ImageMeta(
            filename=clean_filename,
            format=detected_format if detected_format != "MPO" else "JPEG",
            width=orig_w,
            height=orig_h,
            stored_width=stored_w,
            stored_height=stored_h,
            inference_width=inf_w,
            inference_height=inf_h,
            resize_factor=scale,
            scale_mode=scale_mode,
            warnings=warnings,
        )

        return oriented_img, inf_img, image_meta

    @classmethod
    def save_stored_image(cls, inspection_id: str, image: Image.Image) -> Path:
        """Sauvegarde l'image orientée au format PNG dans le stockage persistant."""
        target_dir = cls.get_inspection_dir(inspection_id)
        out_path = target_dir / "original.png"
        image.save(out_path, format="PNG")
        return out_path

    @classmethod
    def get_stored_image_path(cls, inspection_id: str) -> Path:
        """Renvoie le chemin de l'image stockée."""
        path = cls.get_inspection_dir(inspection_id) / "original.png"
        if not path.exists():
            raise FileNotFoundError(f"Image originale manquante pour l'inspection {inspection_id}")
        return path

    @classmethod
    def save_raw_map(cls, inspection_id: str, raw_map: np.ndarray) -> Path:
        """Sauvegarde la carte brute float32 PatchCore (non servie via HTTP)."""
        target_dir = cls.get_inspection_dir(inspection_id)
        out_path = target_dir / "raw_map.npy"
        np.save(out_path, raw_map.astype(np.float32))
        return out_path

    @classmethod
    def save_heatmap_png(cls, inspection_id: str, heatmap_img: Image.Image) -> Path:
        """Sauvegarde la carte de chaleur normalisée au format PNG 8-bit."""
        target_dir = cls.get_inspection_dir(inspection_id)
        out_path = target_dir / "heatmap.png"
        heatmap_img.save(out_path, format="PNG")
        return out_path

    @classmethod
    def get_heatmap_path(cls, inspection_id: str) -> Path:
        path = cls.get_inspection_dir(inspection_id) / "heatmap.png"
        if not path.exists():
            raise FileNotFoundError(f"Heatmap introuvable pour l'inspection {inspection_id}")
        return path

    @classmethod
    def save_overlay_png(cls, inspection_id: str, overlay_img: Image.Image) -> Path:
        """Sauvegarde l'overlay visuel au format PNG."""
        target_dir = cls.get_inspection_dir(inspection_id)
        out_path = target_dir / "overlay.png"
        overlay_img.save(out_path, format="PNG")
        return out_path

    @classmethod
    def get_overlay_path(cls, inspection_id: str) -> Path:
        path = cls.get_inspection_dir(inspection_id) / "overlay.png"
        if not path.exists():
            raise FileNotFoundError(f"Overlay introuvable pour l'inspection {inspection_id}")
        return path

    @classmethod
    def save_export_json(cls, inspection_id: str, json_str: str) -> Path:
        target_dir = cls.get_inspection_dir(inspection_id)
        out_path = target_dir / "export.json"
        out_path.write_text(json_str, encoding="utf-8")
        return out_path

    @classmethod
    def get_export_path(cls, inspection_id: str) -> Path:
        path = cls.get_inspection_dir(inspection_id) / "export.json"
        if not path.exists():
            raise FileNotFoundError(f"Export introuvable pour l'inspection {inspection_id}")
        return path

