"""Polished, resume-grounded interview report PDFs."""

from __future__ import annotations

import html
import os
from io import BytesIO
from pathlib import Path
from typing import Any

from django.conf import settings


def _font_paths() -> list[Path]:
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    windows_dir = Path(str(Path.home()))
    windir = Path(str(os.environ.get("WINDIR", "C:/Windows")))
    paths = [
        base_dir / "users" / "static" / "users" / "fonts" / "Nirmala.ttf",
        base_dir / "users" / "static" / "users" / "fonts" / "NirmalaUI.ttf",
        base_dir / "users" / "static" / "users" / "fonts" / "Mangal.ttf",
        base_dir / "static" / "fonts" / "NotoSansDevanagari-Regular.ttf",
        windir / "Fonts" / "Nirmala.ttf",
        windir / "Fonts" / "NirmalaUI.ttf",
        windir / "Fonts" / "Mangal.ttf",
        windows_dir / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts" / "Nirmala.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
        Path("/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf"),
    ]
    configured_path = str(getattr(settings, "REPORT_PDF_FONT_PATH", "")).strip()
    if configured_path:
        paths.insert(0, Path(configured_path))
    return paths


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular = "Helvetica"
    bold = "Helvetica-Bold"
    for font_path in _font_paths():
        if not font_path.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont("CareerAIUnicode", str(font_path)))
            regular = "CareerAIUnicode"
            bold = "CareerAIUnicode"
            break
        except Exception:
            continue
    return regular, bold


def _paragraph_text(value: Any) -> str:
    text = html.escape(str(value or "").strip())
    return text.replace("\r\n", "\n").replace("\n", "<br/>") or "-"


def _list_items(items: Any, limit: int = 6) -> list[str]:
    if not isinstance(items, list):
        return []
    result = []
    for item in items[:limit]:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result


def _answer_map(feedback) -> dict[int, dict[str, Any]]:
    values = getattr(feedback, "professional_answers", []) or []
    if not isinstance(values, list):
        return {}
    result = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        try:
            result[int(item.get("order"))] = item
        except (TypeError, ValueError):
            continue
    return result


def build_interview_report_pdf(session) -> bytes:
    """Return a complete PDF report for one completed InterviewSession."""

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            KeepTogether,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:  # pragma: no cover - dependency is declared in requirements
        raise RuntimeError("reportlab is not installed. Run pip install -r requirements.txt") from exc

    regular_font, bold_font = _register_fonts()
    purple = colors.HexColor("#4f46e5")
    dark_purple = colors.HexColor("#312e81")
    ink = colors.HexColor("#111827")
    muted = colors.HexColor("#6b7280")
    light_purple = colors.HexColor("#f5f3ff")
    line = colors.HexColor("#e5e7eb")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CareerAITitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=25,
        leading=30,
        textColor=ink,
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "CareerAISubtitle",
        parent=styles["Normal"],
        fontName=regular_font,
        fontSize=10,
        leading=15,
        textColor=muted,
        spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "CareerAISection",
        parent=styles["Heading2"],
        fontName=bold_font,
        fontSize=15,
        leading=20,
        textColor=dark_purple,
        spaceBefore=14,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "CareerAIBody",
        parent=styles["BodyText"],
        fontName=regular_font,
        fontSize=9.5,
        leading=14,
        textColor=ink,
        spaceAfter=5,
    )
    small_style = ParagraphStyle(
        "CareerAISmall",
        parent=body_style,
        fontSize=8,
        leading=11,
        textColor=muted,
    )
    question_style = ParagraphStyle(
        "CareerAIQuestion",
        parent=body_style,
        fontName=bold_font,
        fontSize=11,
        leading=15,
        textColor=ink,
        spaceAfter=6,
    )
    answer_label_style = ParagraphStyle(
        "CareerAIAnswerLabel",
        parent=body_style,
        fontName=bold_font,
        fontSize=8.5,
        leading=11,
        textColor=purple,
        spaceAfter=4,
    )
    center_small_style = ParagraphStyle(
        "CareerAICenterSmall",
        parent=small_style,
        alignment=TA_CENTER,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title="CareerAI Interview Report",
        author="CareerAI",
    )

    def draw_header_footer(canvas, document):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(purple)
        canvas.rect(0, height - 8 * mm, width, 8 * mm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.white)
        canvas.drawString(17 * mm, height - 5.2 * mm, "CareerAI")
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(muted)
        canvas.drawString(17 * mm, 9 * mm, "CareerAI · Resume-grounded interview practice")
        canvas.drawRightString(width - 17 * mm, 9 * mm, f"Page {document.page}")
        canvas.restoreState()

    feedback = getattr(session, "feedback", None)
    feedback = feedback if feedback is not None else type("EmptyFeedback", (), {})()
    questions = list(session.questions.all().prefetch_related("answer"))
    answer_map = _answer_map(feedback)
    story = []

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("CareerAI Interview Report", title_style))
    started = getattr(session, "started_at", None)
    date_text = started.strftime("%d %b %Y") if started else ""
    story.append(
        Paragraph(
            _paragraph_text(f"{session.role} · {str(session.difficulty).title()} · {date_text}"),
            subtitle_style,
        )
    )

    score = float(session.overall_score or 0)
    score_table = Table(
        [
            [
                Paragraph("<b>OVERALL SCORE</b><br/><font size=24 color='#312e81'>" + f"{score:.1f}" + "</font><font size=10 color='#6b7280'> / 100</font>", center_small_style),
                Paragraph(_paragraph_text(f"{len(questions)} questions completed"), center_small_style),
                Paragraph(_paragraph_text(str(getattr(feedback, "generated_by", "local")).upper() + " FEEDBACK"), center_small_style),
            ]
        ],
        colWidths=[55 * mm, 55 * mm, 55 * mm],
    )
    score_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), light_purple),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#ddd6fe")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e9e5ff")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(score_table)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Coach summary", section_style))
    summary_data = []
    for label, values in (
        ("Strengths", _list_items(getattr(feedback, "strengths", []))),
        ("Focus areas", _list_items(getattr(feedback, "weaknesses", []))),
        ("Next steps", _list_items(getattr(feedback, "recommendations", []))),
    ):
        rendered = "<br/>".join(f"• {_paragraph_text(value)}" for value in values) or "-"
        summary_data.append([Paragraph(f"<b>{html.escape(label)}</b>", body_style), Paragraph(rendered, body_style)])
    summary_table = Table(summary_data, colWidths=[32 * mm, 133 * mm], hAlign="LEFT")
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), light_purple),
                ("BOX", (0, 0), (-1, -1), 0.5, line),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, line),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(summary_table)
    story.append(Paragraph("Professional answers are practice models. Replace any generic wording with your exact contribution and verified results before using it in a real interview.", small_style))
    story.append(PageBreak())
    story.append(Paragraph("Question-by-question answer key", section_style))
    story.append(Paragraph("Every answer is grounded in the resume evidence used to create this interview and is provided in English and Hindi.", subtitle_style))

    for index, question in enumerate(questions, start=1):
        item = answer_map.get(int(question.order), {})
        professional_en = item.get("answer_en", "Professional answer was not stored for this question.")
        professional_hi = item.get("answer_hi", "इस प्रश्न के लिए professional answer उपलब्ध नहीं है।")
        evidence = item.get("source_evidence", question.source_evidence)
        candidate_answer = getattr(getattr(question, "answer", None), "answer_text", "")
        candidate_score = getattr(getattr(question, "answer", None), "overall_score", None)
        heading = Paragraph(f"<font color='#4f46e5'><b>Q{index:02d}</b></font>  {_paragraph_text(question.question_text)}", question_style)
        evidence_text = Paragraph(f"<b>Resume evidence:</b> {_paragraph_text(evidence)}", small_style)
        english_box = Table([[Paragraph("PROFESSIONAL ANSWER · ENGLISH", answer_label_style), Paragraph(_paragraph_text(professional_en), body_style)]], colWidths=[45 * mm, 120 * mm])
        english_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8faff")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c7d2fe")),
            ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        hindi_box = Table([[Paragraph("PROFESSIONAL ANSWER · हिन्दी", answer_label_style), Paragraph(_paragraph_text(professional_hi), body_style)]], colWidths=[45 * mm, 120 * mm])
        hindi_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffdf7")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fde68a")),
            ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        parts = [heading, evidence_text, Spacer(1, 1.5 * mm), english_box, Spacer(1, 2 * mm), hindi_box]
        if candidate_answer:
            score_text = f" · Score: {float(candidate_score):.1f}/100" if candidate_score is not None else ""
            candidate_box = Table([[Paragraph(f"<b>YOUR ANSWER{html.escape(score_text)}</b><br/>{_paragraph_text(candidate_answer)}", small_style)]], colWidths=[165 * mm])
            candidate_box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fafb")),
                ("BOX", (0, 0), (-1, -1), 0.5, line),
                ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]))
            parts.extend([Spacer(1, 2 * mm), candidate_box])
        parts.append(Spacer(1, 6 * mm))
        story.append(KeepTogether(parts))

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("End of report · Keep practising with a new resume-grounded interview to get a different question set.", small_style))
    doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
    return buffer.getvalue()
