"""Génération du rapport d'inspection au format PDF (reportlab).

Le rapport reprend strictement les données déjà persistées (inspection, régions, décisions humaines) :
aucune métrique de performance ML n'est calculée ni affichée (§14.2).
"""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape

FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "DejaVuSans.ttf"
FONT_NAME = "DejaVuSans"
BRAND = colors.HexColor("#4f46e5")
MUTED = colors.HexColor("#64748b")
LINE = colors.HexColor("#e2e8f0")

DECISION_LABELS = {
    "confirmed": "Confirmée",
    "rejected": "Rejetée",
    "uncertain": "Incertaine",
}
STATUS_LABELS = {"pending": "En attente", "running": "En cours", "done": "Terminée", "error": "Échec"}
ENGINE_LABELS = {"yolo": "YOLOv11 (supervisé)", "patchcore": "PatchCore (anomalies)", "similarity": "Similarité"}

_fonts_ready = False


def _ensure_fonts() -> str:
    """Enregistre DejaVu Sans (accents, τ, •) ; repli sur Helvetica si le fichier est absent."""
    global _fonts_ready
    if _fonts_ready:
        return FONT_NAME
    if FONT_PATH.exists():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))
        pdfmetrics.registerFontFamily(FONT_NAME, normal=FONT_NAME, bold=FONT_NAME, italic=FONT_NAME, boldItalic=FONT_NAME)
        _fonts_ready = True
        return FONT_NAME
    return "Helvetica"


def _fmt_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M UTC") if value.tzinfo else value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, str) and value:
        try:
            return _fmt_dt(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return value
    return "—"


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text)) if text is not None else "—", style)


def build_inspection_pdf(
    inspection: Dict[str, Any],
    regions: List[Dict[str, Any]],
    overlay_path: Optional[Path] = None,
    generated_at: Optional[datetime] = None,
) -> bytes:
    font = _ensure_fonts()
    generated_at = generated_at or datetime.now(timezone.utc)

    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["BodyText"], fontName=font, fontSize=9, leading=12, alignment=TA_LEFT)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10, textColor=MUTED)
    cell = ParagraphStyle("cell", parent=body, fontSize=8, leading=10)
    h1 = ParagraphStyle("h1", parent=body, fontSize=20, leading=24, textColor=BRAND)
    h2 = ParagraphStyle("h2", parent=body, fontSize=12, leading=15, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#0f172a"))

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=2 * cm,
        title=f"Rapport d'inspection {inspection.get('id', '')}",
        author="WeaveGuard AI",
    )
    content_width = A4[0] - 4 * cm
    story: List[Any] = []

    # ---- En-tête
    story.append(Paragraph("WeaveGuard AI", h1))
    story.append(_p("Rapport d'inspection textile", ParagraphStyle("sub", parent=body, fontSize=11, textColor=MUTED)))
    story.append(Spacer(1, 10))

    meta = inspection.get("image_meta") or {}
    meta_rows = [
        ["Identifiant", inspection.get("id", "—")],
        ["Statut", STATUS_LABELS.get(inspection.get("status"), inspection.get("status", "—"))],
        ["Soumise le", _fmt_dt(inspection.get("created_at"))],
        ["Terminée le", _fmt_dt(inspection.get("completed_at"))],
        ["Opérateur", inspection.get("created_by", "—")],
        ["Fichier", meta.get("filename", "—")],
        ["Dimensions", f"{meta.get('stored_width', '?')} × {meta.get('stored_height', '?')} px" if meta else "—"],
    ]
    if inspection.get("is_demo"):
        meta_rows.append(["Origine", "Donnée de démonstration"])
    t = Table([[_p(k, small), _p(v, body)] for k, v in meta_rows], colWidths=[3.2 * cm, content_width - 3.2 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story.append(t)

    # ---- Synthèse
    yolo = sum(1 for r in regions if r.get("engine") == "yolo")
    pc = sum(1 for r in regions if r.get("engine") == "patchcore")
    decisions = [r.get("latest_decision") for r in regions]
    story.append(Paragraph("Synthèse", h2))
    summary = [
        ["Régions détectées", len(regions), "YOLOv11", yolo, "PatchCore", pc],
        ["Confirmées", decisions.count("confirmed"), "Rejetées", decisions.count("rejected"),
         "Incertaines", decisions.count("uncertain")],
    ]
    st = Table([[(_p(c, small) if i % 2 == 0 else _p(c, ParagraphStyle("n", parent=body, fontSize=13, leading=15, textColor=BRAND)))
                 for i, c in enumerate(row)] for row in summary],
               colWidths=[content_width / 6] * 6)
    st.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.25, LINE),
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story.append(st)
    if not regions and inspection.get("status") == "done":
        story.append(Spacer(1, 6))
        story.append(_p("Aucune région détectée par les moteurs exécutés. Ce résultat n'est pas une garantie d'absence de défaut.", body))

    # ---- Moteurs
    engines = inspection.get("engines") or {}
    if engines:
        story.append(Paragraph("Moteurs d'analyse", h2))
        rows = [[_p(h, small) for h in ("Moteur", "État", "Version", "Latence totale")]]
        for name, info in engines.items():
            info = info or {}
            lat = (info.get("latency_ms") or {}).get("total")
            rows.append([
                _p(ENGINE_LABELS.get(name, name), cell),
                _p(info.get("status", "—") + (f" — {info['error']}" if info.get("error") else ""), cell),
                _p((info.get("version") or "—")[:24], cell),
                _p(f"{lat:.0f} ms" if isinstance(lat, (int, float)) else "—", cell),
            ])
        et = Table(rows, colWidths=[5 * cm, content_width - 5 * cm - 6 * cm, 3.6 * cm, 2.4 * cm], repeatRows=1)
        et.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(et)

    # ---- Avertissements
    warnings = list(inspection.get("warnings") or [])
    dc = inspection.get("domain_check") or {}
    if dc.get("status") == "below_range":
        warnings.append(
            f"Domaine : similarité max {dc.get('max_similarity')} < minimum de référence {dc.get('reference_min')} — "
            "l'image ressemble peu aux données d'apprentissage ; interpréter les résultats avec prudence."
        )
    if inspection.get("partial"):
        warnings.append("Résultat partiel : au moins un moteur d'analyse a échoué.")
    if warnings:
        story.append(Paragraph("Avertissements", h2))
        for w in warnings:
            story.append(_p(f"• {w}", body))

    # ---- Image annotée
    if overlay_path and Path(overlay_path).exists():
        with PILImage.open(overlay_path) as im:
            w_px, h_px = im.size
        max_h = 12.5 * cm
        scale = min(content_width / w_px, max_h / h_px)
        # Le titre reste solidaire de l'image (pas de titre orphelin en bas de page)
        story.append(KeepTogether([
            Paragraph("Image annotée", h2),
            Image(str(overlay_path), width=w_px * scale, height=h_px * scale),
        ]))

    # ---- Régions
    if regions:
        story.append(Paragraph("Régions détectées", h2))
        head = [_p(h, small) for h in ("ID", "Moteur", "Libellé", "Score", "Boîte [x, y, l, h]", "Décision")]
        rows = [head]
        for r in regions:
            bbox = r.get("bbox") or []
            score = r.get("score")
            rows.append([
                _p(r.get("display_id") or str(r.get("id", ""))[:6], cell),
                _p("YOLO" if r.get("engine") == "yolo" else "PatchCore", cell),
                _p(r.get("classification") or r.get("label") or "—", cell),
                _p(f"{score:.2f}" if isinstance(score, (int, float)) else "—", cell),
                _p("[" + ", ".join(str(round(v)) for v in bbox) + "]" if bbox else "—", cell),
                _p(DECISION_LABELS.get(r.get("latest_decision"), "Non revue"), cell),
            ])
        rt = Table(rows, colWidths=[1.3 * cm, 2.2 * cm, content_width - 1.3 * cm - 2.2 * cm - 1.6 * cm - 4.4 * cm - 2.4 * cm,
                                    1.6 * cm, 4.4 * cm, 2.4 * cm], repeatRows=1)
        rt.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")])]))
        story.append(rt)

    story.append(Spacer(1, 14))
    story.append(KeepTogether([_p(
        "Les scores YOLO sont des confiances modèle ; les scores PatchCore sont des distances d'anomalie. "
        "Ils ne sont pas comparables entre eux. Ce rapport est une aide à la décision et ne remplace pas la revue humaine.",
        small)]))

    def _footer(canvas, document):
        canvas.saveState()
        canvas.setFont(font, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(2 * cm, 1.1 * cm, f"WeaveGuard AI — rapport généré le {_fmt_dt(generated_at)}")
        canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Page {document.page}")
        canvas.setStrokeColor(BRAND)
        canvas.setLineWidth(1.5)
        canvas.line(2 * cm, A4[1] - 1.2 * cm, A4[0] - 2 * cm, A4[1] - 1.2 * cm)
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
