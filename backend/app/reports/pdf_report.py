import io
import json
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Flowable,
)

GRADE_COLORS = {
    "A": colors.HexColor("#10b981"),
    "B": colors.HexColor("#84cc16"),
    "C": colors.HexColor("#eab308"),
    "D": colors.HexColor("#f97316"),
    "E": colors.HexColor("#ea580c"),
    "F": colors.HexColor("#dc2626"),
    "N/A": colors.HexColor("#9ca3af"),
}

CATEGORY_META = {
    "headers": ("HTTP Security Headers", colors.HexColor("#3b82f6")),
    "tls": ("TLS / SSL", colors.HexColor("#8b5cf6")),
    "dns": ("DNS / Email Security", colors.HexColor("#06b6d4")),
    "cookies": ("Cookie Security", colors.HexColor("#f59e0b")),
}

INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
LIGHT = colors.HexColor("#f1f5f9")
BORDER = colors.HexColor("#e2e8f0")
GREEN = colors.HexColor("#15803d")
RED = colors.HexColor("#b91c1c")
AMBER = colors.HexColor("#b45309")


class ScoreBar(Flowable):
    """A horizontal progress bar showing a 0-100 score."""
    def __init__(self, score, width=150, height=7, color=colors.HexColor("#10b981")):
        super().__init__()
        self.score = max(0, min(100, score))
        self.width = width
        self.height = height
        self.color = color

    def draw(self):
        c = self.canv
        # track
        c.setFillColor(BORDER)
        c.roundRect(0, 0, self.width, self.height, self.height / 2, fill=1, stroke=0)
        # fill
        fill_w = self.width * (self.score / 100)
        if fill_w > 0:
            c.setFillColor(self.color)
            c.roundRect(0, 0, max(fill_w, self.height), self.height,
                        self.height / 2, fill=1, stroke=0)


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="H1", fontName="Helvetica-Bold", fontSize=20,
                              leading=24, textColor=colors.white))
    styles.add(ParagraphStyle(name="HSub", fontSize=9.5, leading=13,
                              textColor=colors.HexColor("#cbd5e1")))
    styles.add(ParagraphStyle(name="Sub", fontSize=9, leading=13, textColor=MUTED))
    styles.add(ParagraphStyle(name="SectionHead", fontName="Helvetica-Bold",
                              fontSize=13, leading=16, textColor=INK,
                              spaceBefore=12, spaceAfter=8))
    styles.add(ParagraphStyle(name="CatTitle", fontName="Helvetica-Bold",
                              fontSize=11, leading=14, textColor=INK))
    styles.add(ParagraphStyle(name="CheckName", fontName="Helvetica-Bold",
                              fontSize=8.5, leading=11, textColor=INK))
    styles.add(ParagraphStyle(name="CheckDetail", fontSize=8, leading=10.5,
                              textColor=MUTED))
    styles.add(ParagraphStyle(name="Advice", fontSize=7.5, leading=10,
                              textColor=AMBER))
    styles.add(ParagraphStyle(name="Stat", fontName="Helvetica-Bold", fontSize=16,
                              leading=18, textColor=INK, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="StatLabel", fontSize=7.5, leading=10,
                              textColor=MUTED, alignment=TA_CENTER))
    return styles


def _truncate(text, limit=140):
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def _fmt_date(iso_str):
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", ""))
        return dt.strftime("%d %b %Y, %H:%M")
    except (ValueError, TypeError):
        return str(iso_str)


def generate_domain_report(domain_url: str, scans: list[dict]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=0, bottomMargin=16 * mm,
        leftMargin=16 * mm, rightMargin=16 * mm,
        title=f"SiteShield Report - {domain_url}",
    )
    styles = _styles()
    story = []
    content_w = doc.width

    # ---- Header band (full-width dark) ----
    header_inner = Table(
        [[Paragraph("&#128737; SiteShield Security Report", styles["H1"])],
         [Paragraph(domain_url, styles["HSub"])],
         [Paragraph(f"Generated {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}",
                    styles["HSub"])]],
        colWidths=[content_w + 32 * mm],
    )
    header_inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK),
        ("LEFTPADDING", (0, 0), (-1, -1), 16 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16 * mm),
        ("TOPPADDING", (0, 0), (0, 0), 16),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 16),
        ("TOPPADDING", (0, 1), (-1, -1), 1),
    ]))
    story.append(header_inner)
    story.append(Spacer(1, 14))

    if not scans:
        story.append(Paragraph("No scans available for this domain yet.", styles["Sub"]))
        doc.build(story)
        return buffer.getvalue()

    latest = scans[0]
    grade = latest.get("grade", "N/A")
    score = latest.get("score", 0)
    grade_color = GRADE_COLORS.get(grade, colors.HexColor("#9ca3af"))

    # ---- Grade badge + summary stats strip ----
    grades_only = [s.get("grade") for s in scans]
    best = max((s.get("score", 0) for s in scans), default=0)

    badge_cell = Table([[Paragraph(
        f'<font color="white" size="30"><b>{grade}</b></font>', styles["Stat"])]],
        colWidths=[26 * mm], rowHeights=[26 * mm])
    badge_cell.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), grade_color),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))

    def stat(value, label):
        return Table([[Paragraph(str(value), styles["Stat"])],
                      [Paragraph(label, styles["StatLabel"])]])

    summary = Table([[
        badge_cell,
        stat(f"{score}/100", "CURRENT SCORE"),
        stat(f"{best}/100", "BEST SCORE"),
        stat(len(scans), "TOTAL SCANS"),
    ]], colWidths=[30 * mm, content_w / 3 - 10 * mm,
                   content_w / 3 - 10 * mm, content_w / 3 - 10 * mm])
    summary.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (1, 0), (-1, -1), LIGHT),
        ("LINEAFTER", (1, 0), (2, 0), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary)
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Latest scan: {_fmt_date(latest.get('created_at'))}",
                           styles["Sub"]))

    # ---- Category breakdown ----
    categories = latest.get("categories")
    if categories:
        story.append(Paragraph("Latest Scan — Category Breakdown", styles["SectionHead"]))
        for key, (label, accent) in CATEGORY_META.items():
            cat = categories.get(key)
            if not cat:
                continue
            cat_score = cat.get("score", 0)
            unreachable = cat.get("unreachable", False)

            # Category header row: title + score bar + score
            if unreachable:
                header_row = Table([[
                    Paragraph(label, styles["CatTitle"]),
                    Paragraph("Unreachable — not scored", styles["Sub"]),
                ]], colWidths=[content_w * 0.5, content_w * 0.5])
            else:
                header_row = Table([[
                    Paragraph(label, styles["CatTitle"]),
                    ScoreBar(cat_score, width=content_w * 0.30, color=accent),
                    Paragraph(f"<b>{cat_score}/100</b>", styles["CheckName"]),
                ]], colWidths=[content_w * 0.45, content_w * 0.35, content_w * 0.20])
            header_row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, accent),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(header_row)

            # Check rows
            check_rows = []
            for check in cat.get("checks", []):
                passed = check.get("passed", check.get("present", False))
                name = check.get("name", check.get("header", "Check"))
                detail = _truncate(check.get("detail") or check.get("value") or "")
                mark = "PASS" if passed else "FAIL"
                mark_color = GREEN if passed else RED
                advice = check.get("advice")

                left = [Paragraph(name, styles["CheckName"])]
                if detail:
                    left.append(Paragraph(detail, styles["CheckDetail"]))
                if not passed and advice:
                    left.append(Paragraph(f"&#8594; {advice}", styles["Advice"]))

                check_rows.append([
                    Paragraph(f'<font color="{"#15803d" if passed else "#b91c1c"}"><b>{mark}</b></font>',
                              styles["CheckDetail"]),
                    left,
                    Paragraph(f'{check.get("weight", "")} pts' if check.get("weight") else "",
                              styles["CheckDetail"]),
                ])
            if check_rows:
                ct = Table(check_rows, colWidths=[14 * mm, content_w - 34 * mm, 18 * mm])
                ct.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ]))
                story.append(ct)
            story.append(Spacer(1, 8))

    # ---- Scan history table ----
    story.append(Paragraph("Scan History", styles["SectionHead"]))
    rows = [["Date", "Grade", "Score"]]
    for s in scans:
        rows.append([_fmt_date(s.get("created_at")),
                     s.get("grade", "N/A"), f"{s.get('score', 0)}/100"])
    table = Table(rows, colWidths=[content_w * 0.5, content_w * 0.25, content_w * 0.25])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(table)

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "SiteShield performs passive, non-intrusive analysis of publicly observable "
        "configuration. This report reflects the security posture at the times scanned.",
        ParagraphStyle("foot", fontSize=7.5, leading=10, textColor=MUTED,
                       borderColor=BORDER, borderWidth=0, spaceBefore=4),
    ))

    doc.build(story)
    return buffer.getvalue()