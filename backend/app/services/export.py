"""Note export helpers: Markdown passthrough and PDF rendering (reportlab)."""
from __future__ import annotations

import io
import re


def to_pdf(markdown: str, title: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title or "ORAYA notes",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("OrayaH1", parent=styles["Heading1"], fontSize=18, leading=22, textColor="#1B1B1A")
    h2 = ParagraphStyle("OrayaH2", parent=styles["Heading2"], fontSize=13, leading=17, textColor="#E8705B")
    body = ParagraphStyle("OrayaBody", parent=styles["BodyText"], fontSize=10.5, leading=15, textColor="#1B1B1A")
    bullet = ParagraphStyle("OrayaBullet", parent=body, leftIndent=12, bulletIndent=2)

    story = []
    for raw in markdown.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            story.append(Spacer(1, 6))
            continue
        text = _inline(line)
        if line.startswith("### "):
            story.append(Paragraph(text[4:], h2))
        elif line.startswith("## "):
            story.append(Paragraph(text[3:], h2))
        elif line.startswith("# "):
            story.append(Paragraph(text[2:], h1))
        elif line.lstrip().startswith(("- ", "* ")):
            story.append(Paragraph(_escape(line.lstrip()[2:]), bullet, bulletText="•"))
        else:
            story.append(Paragraph(text, body))
    if not story:
        story.append(Paragraph("(empty note)", body))
    doc.build(story)
    return buf.getvalue()


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(line: str) -> str:
    """Escape XML then re-apply inline markdown as reportlab tags."""
    text = _escape(line)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    return text
