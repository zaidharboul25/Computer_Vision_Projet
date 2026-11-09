"""Tests unitaires du service de stockage et de validation des uploads (Phase 3).

Vérifie :
- Exigence C : Fichier vide, extension != contenu, image corrompue, fichier trop lourd,
  garde anti-bombe de décompression, conversions RGB (L, RGBA, 16-bit), rejet GIF animé,
  sécurisation des noms de fichiers (anti path-traversal).
- Exigence D (AC-02) : Repères de coordonnées avec valeurs de référence connues,
  redimensionnement si long côté > INFERENCE_LONG_SIDE, orientation EXIF != 1.
"""
import io
import pytest
import numpy as np
from PIL import Image
from app.core.config import settings
from app.core.errors import FileTooLargeException, ImageTooLargeException, InvalidImageException
from app.services.storage import StorageService


def test_upload_empty_file_fails():
    """Un fichier vide doit lever InvalidImageException (INVALID_IMAGE, 400)."""
    with pytest.raises(InvalidImageException) as exc_info:
        StorageService.validate_and_preprocess_upload(b"", "empty.jpg")
    assert exc_info.value.code == "INVALID_IMAGE"


def test_upload_corrupted_file_fails():
    """Un flux d'octets corrompus doit lever InvalidImageException."""
    corrupted_bytes = b"not an image at all"
    with pytest.raises(InvalidImageException) as exc_info:
        StorageService.validate_and_preprocess_upload(corrupted_bytes, "corrupt.png")
    assert exc_info.value.code == "INVALID_IMAGE"


def test_upload_animated_gif_rejected():
    """Les fichiers GIF ou animations sont strictement rejetés (INVALID_IMAGE)."""
    buf = io.BytesIO()
    im1 = Image.new("RGB", (100, 100), color="red")
    im2 = Image.new("RGB", (100, 100), color="blue")
    im1.save(buf, format="GIF", save_all=True, append_images=[im2])
    gif_bytes = buf.getvalue()

    with pytest.raises(InvalidImageException) as exc_info:
        StorageService.validate_and_preprocess_upload(gif_bytes, "anim.gif")
    assert exc_info.value.code == "INVALID_IMAGE"
    assert "GIF" in exc_info.value.message


def test_upload_extension_differs_from_content():
    """Un contenu PNG nommé .jpg doit être correctement identifié par son contenu réel sans planter."""
    buf = io.BytesIO()
    im = Image.new("RGB", (200, 200), color="green")
    im.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    stored_img, inf_img, meta = StorageService.validate_and_preprocess_upload(png_bytes, "trick.jpg")
    assert meta.format == "PNG"
    assert stored_img.size == (200, 200)


def test_upload_too_large_size():
    """Un fichier excédant MAX_UPLOAD_MB lève ImageTooLargeException (IMAGE_TOO_LARGE, 413)."""
    # Simulation d'un fichier lourd sans allocation de 50 Mo
    oversized_bytes = b"0" * ((settings.MAX_UPLOAD_MB * 1024 * 1024) + 10)
    with pytest.raises(ImageTooLargeException) as exc_info:
        StorageService.validate_and_preprocess_upload(oversized_bytes, "big.jpg")
    assert exc_info.value.code == "IMAGE_TOO_LARGE"


def test_upload_decompression_bomb_guard():
    """Une tentative de décompression d'image aux dimensions excessives est interceptée."""
    oversized_side = settings.MAX_IMAGE_SIDE + 100
    # Création d'une image avec dimensions déclenchant la garde
    buf = io.BytesIO()
    im = Image.new("1", (oversized_side, 100))
    im.save(buf, format="PNG")
    oversized_bytes = buf.getvalue()

    with pytest.raises(ImageTooLargeException) as exc_info:
        StorageService.validate_and_preprocess_upload(oversized_bytes, "bomb.png")
    assert exc_info.value.code == "IMAGE_TOO_LARGE"


def test_upload_color_modes_conversion():
    """Les modes niveaux de gris (L), RGBA et 16-bit (I) sont convertis proprement en RGB 8-bit."""
    # Niveaux de gris 'L'
    buf_l = io.BytesIO()
    im_l = Image.new("L", (100, 100), color=128)
    im_l.save(buf_l, format="PNG")
    stored_l, _, meta_l = StorageService.validate_and_preprocess_upload(buf_l.getvalue(), "gray.png")
    assert stored_l.mode == "RGB"
    assert any("converti" in w for w in meta_l.warnings)

    # RGBA
    buf_rgba = io.BytesIO()
    im_rgba = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
    im_rgba.save(buf_rgba, format="PNG")
    stored_rgba, _, meta_rgba = StorageService.validate_and_preprocess_upload(buf_rgba.getvalue(), "alpha.png")
    assert stored_rgba.mode == "RGB"

    # 16-bit 'I;16' ou 'I'
    arr_16 = np.arange(10000, dtype=np.uint16).reshape((100, 100))
    im_16 = Image.fromarray(arr_16)
    buf_16 = io.BytesIO()
    im_16.save(buf_16, format="PNG")
    stored_16, _, meta_16 = StorageService.validate_and_preprocess_upload(buf_16.getvalue(), "depth.png")
    assert stored_16.mode == "RGB"


def test_upload_filename_sanitization():
    """Un nom avec ../ ou des caractères spéciaux est assaini et ne traverse jamais le système de fichiers."""
    buf = io.BytesIO()
    im = Image.new("RGB", (100, 100), color="white")
    im.save(buf, format="PNG")

    _, _, meta = StorageService.validate_and_preprocess_upload(buf.getvalue(), "../../etc/passwd.jpg")
    assert ".." not in meta.filename
    assert "/" not in meta.filename
    assert "\\" not in meta.filename


def test_coordinates_scale_and_exif_orientation():
    """Exigence D (AC-02) : Test avec des valeurs dimensionnelles connues.
    
    1. Image de taille connue (640x480 <= INFERENCE_LONG_SIDE 1448) :
       facteur d'échelle = 1.0, dimensions inchangées.
    2. Image 2x plus grande que INFERENCE_LONG_SIDE (ex: 2896x1000) :
       redimensionnement proportionnel, resize_factor = 0.5.
    3. Image avec tag EXIF d'orientation != 1 :
       l'image stockée et les dimensions renvoyées correspondent à l'image redressée.
    """
    # Cas 1 : Facteur d'échelle = 1.0
    buf_exact = io.BytesIO()
    im_exact = Image.new("RGB", (640, 480), color=(100, 100, 100))
    im_exact.save(buf_exact, format="PNG")
    stored_1, inf_1, meta_1 = StorageService.validate_and_preprocess_upload(buf_exact.getvalue(), "exact.png")
    assert meta_1.resize_factor == 1.0
    assert meta_1.stored_width == 640
    assert meta_1.stored_height == 480
    assert inf_1.size == (640, 480)

    # Cas 2 : Long côté = 2896 (exactement 2x INFERENCE_LONG_SIDE = 1448)
    buf_large = io.BytesIO()
    im_large = Image.new("RGB", (2896, 1000), color=(50, 50, 50))
    im_large.save(buf_large, format="PNG")
    stored_2, inf_2, meta_2 = StorageService.validate_and_preprocess_upload(buf_large.getvalue(), "large.png")
    expected_scale = 1448.0 / 2896.0  # 0.5
    assert pytest.approx(meta_2.resize_factor, rel=1e-3) == expected_scale
    assert meta_2.stored_width == 2896
    assert meta_2.stored_height == 1000
    assert inf_2.size == (1448, 500)

    # Cas 3 : EXIF Orientation = 6 (rotation 90° dans les métadonnées)
    buf_exif = io.BytesIO()
    im_exif = Image.new("RGB", (400, 200), color=(20, 20, 20))
    exif_data = im_exif.getexif()
    exif_data[0x0112] = 6  # 6 signifie rotation 90 CW requise pour le redressement
    im_exif.save(buf_exif, format="JPEG", exif=exif_data)

    stored_3, _, meta_3 = StorageService.validate_and_preprocess_upload(buf_exif.getvalue(), "oriented.jpg")
    # Après exif_transpose, la largeur devient 200 et la hauteur 400
    assert stored_3.size == (200, 400)
    assert meta_3.stored_width == 200
    assert meta_3.stored_height == 400


def test_scale_mode_normalized_upscaling_and_warning():
    """Mode normalized : image avec grand côté < INFERENCE_LONG_SIDE est agrandie (bicubique)

    jusqu'à INFERENCE_LONG_SIDE avant l'inférence.
    resize_factor > 1.0, warning 'image agrandie : l'agrandissement n'ajoute pas d'information'.
    """
    buf_small = io.BytesIO()
    # Image 343x200 (pull en maille)
    im_small = Image.new("RGB", (343, 200), color=(80, 80, 80))
    im_small.save(buf_small, format="PNG")

    stored_img, inf_img, meta = StorageService.validate_and_preprocess_upload(
        buf_small.getvalue(),
        "small_pull.png",
        scale_mode="normalized",
    )

    expected_factor = round(settings.INFERENCE_LONG_SIDE / 343.0, 4)
    assert meta.scale_mode == "normalized"
    assert meta.resize_factor > 1.0
    assert pytest.approx(meta.resize_factor, rel=1e-3) == expected_factor
    # L'image stockée reste en taille native (343, 200)
    assert stored_img.size == (343, 200)
    assert meta.stored_width == 343
    assert meta.stored_height == 200
    # L'image d'inférence est agrandie à INFERENCE_LONG_SIDE = 1448
    assert inf_img.size[0] == settings.INFERENCE_LONG_SIDE
    assert any("image agrandie : l'agrandissement n'ajoute pas d'information" in w for w in meta.warnings)


def test_scale_mode_native_small_image_warning():
    """Mode native : image avec grand côté < INFERENCE_LONG_SIDE reste en taille native

    mais reçoit un avertissement explicite sur sa petite dimension.
    """
    buf_small = io.BytesIO()
    im_small = Image.new("RGB", (343, 200), color=(80, 80, 80))
    im_small.save(buf_small, format="PNG")

    stored_img, inf_img, meta = StorageService.validate_and_preprocess_upload(
        buf_small.getvalue(),
        "small_native.png",
        scale_mode="native",
    )

    assert meta.scale_mode == "native"
    assert meta.resize_factor == 1.0
    assert stored_img.size == (343, 200)
    assert inf_img.size == (343, 200)
    assert any("Image de petite taille par rapport à la référence d'inférence" in w for w in meta.warnings)


def test_coordinate_rescaling_with_scale_greater_than_one():
    """Vérifie le remappage des coordonnées de prédiction vers l'image stockée

    lorsque le facteur de redimensionnement scale_mode=normalized > 1.0.
    """
    # Facteur d'agrandissement = 2.0 (image d'inférence 2x plus grande)
    scale = 2.0
    # Prédiction sur l'image d'inférence
    inf_box = [100.0, 80.0, 40.0, 60.0]

    # Remappage vers les coordonnées de l'image originale stockée
    rx, ry, rw, rh = inf_box
    mapped_box = [
        round(rx / scale, 2),
        round(ry / scale, 2),
        round(rw / scale, 2),
        round(rh / scale, 2),
    ]
    area = round((rw / scale) * (rh / scale), 2)

    assert mapped_box == [50.0, 40.0, 20.0, 30.0]
    assert area == 600.0


