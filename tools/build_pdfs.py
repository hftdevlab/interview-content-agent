"""Build styled PDF guides with strict approved-only publication filtering."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import math
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from tools.content import (
    GUIDE_SPECS,
    ROOT,
    QuestionRecord,
    discover_questions,
    is_publication_ready,
    load_project_version,
    question_anchor,
    questions_by_type,
)
from tools.generate_catalog import category_counts, difficulty_counts

try:
    from reportlab import rl_config
    from reportlab.graphics import renderPDF
    from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        BaseDocTemplate,
        Flowable,
        Frame,
        KeepTogether,
        ListFlowable,
        ListItem,
        NextPageTemplate,
        PageBreak,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        XPreformatted,
    )
    from reportlab.platypus.tableofcontents import TableOfContents
except ImportError as exc:  # pragma: no cover - exercised by CLI setup failures
    raise SystemExit(
        "PDF generation requires ReportLab. Run `python -m pip install -e .` "
        "inside the project virtual environment."
    ) from exc


rl_config.invariant = 1

GUIDE_COLORS = {
    "system_design": "#0B6173",
    "coding": "#4C3A78",
    "fundamentals": "#8A482C",
}
ASCII_TRANSLATION = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
)
INLINE_TOKEN = re.compile(
    r"(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\)|https?://[^\s<]+)"
)
IMAGE_LINE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
HEADING_LINE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LIST_LINE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.+)$")
BLOCKQUOTE_LINE = re.compile(r"^>\s?(.*)$")
TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")


def _ascii(value: str) -> str:
    return value.translate(ASCII_TRANSLATION)


def _inline_markup(value: str) -> str:
    """Convert the small inline-Markdown subset used by the guides."""

    value = _ascii(value)
    output: list[str] = []
    cursor = 0
    for match in INLINE_TOKEN.finditer(value):
        output.append(html.escape(value[cursor : match.start()]))
        token = match.group(0)
        if token.startswith("`"):
            output.append(f'<font name="Courier">{html.escape(token[1:-1])}</font>')
        elif token.startswith("**"):
            output.append(f"<b>{html.escape(token[2:-2])}</b>")
        elif token.startswith("["):
            label, target = token[1:].split("](", 1)
            target = target[:-1]
            escaped_label = html.escape(label)
            if target.startswith(("http://", "https://", "#")):
                output.append(
                    f'<link href="{html.escape(target, quote=True)}" '
                    f'color="#155E75">{escaped_label}</link>'
                )
            else:
                output.append(f'<font color="#155E75">{escaped_label}</font>')
        elif token.startswith(("http://", "https://")):
            escaped = html.escape(token)
            output.append(
                f'<link href="{escaped}" color="#155E75">{escaped}</link>'
            )
        cursor = match.end()
    output.append(html.escape(value[cursor:]))
    return "".join(output)


def _styles(
    accent: str,
    *,
    body_leading: float = 13,
) -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    body = ParagraphStyle(
        "GuideBody",
        parent=sample["BodyText"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=body_leading,
        textColor=HexColor("#1F2937"),
        spaceAfter=6,
        allowWidows=0,
        allowOrphans=0,
    )
    return {
        "body": body,
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=31,
            leading=37,
            textColor=colors.white,
            alignment=TA_LEFT,
            spaceAfter=14,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=body,
            fontSize=13,
            leading=19,
            textColor=HexColor("#DCEEF2"),
            spaceAfter=8,
        ),
        "question": ParagraphStyle(
            "QuestionTitle",
            parent=sample["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=21,
            leading=25,
            textColor=HexColor(accent),
            spaceBefore=10,
            spaceAfter=10,
            keepWithNext=True,
        ),
        "h1": ParagraphStyle(
            "GuideH1",
            parent=sample["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=HexColor(accent),
            spaceBefore=10,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "GuideH2",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=17,
            textColor=HexColor("#263B50"),
            spaceBefore=10,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "GuideH3",
            parent=sample["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.8,
            leading=14,
            textColor=HexColor("#374151"),
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "meta": ParagraphStyle(
            "QuestionMeta",
            parent=body,
            fontSize=8.4,
            leading=11,
            textColor=HexColor("#52606D"),
            backColor=HexColor("#EEF4F7"),
            borderPadding=6,
            spaceAfter=10,
        ),
        "bullet": ParagraphStyle(
            "GuideBullet",
            parent=body,
            leftIndent=3,
            firstLineIndent=0,
            spaceAfter=3,
        ),
        "code": ParagraphStyle(
            "GuideCode",
            parent=body,
            fontName="Courier",
            fontSize=6.9,
            leading=9.2,
            textColor=HexColor("#172033"),
            backColor=HexColor("#F3F6F8"),
            borderColor=HexColor("#D4DCE2"),
            borderWidth=0.6,
            borderPadding=7,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "DiagramCaption",
            parent=body,
            fontName="Helvetica-Oblique",
            fontSize=8.1,
            leading=10,
            alignment=TA_CENTER,
            textColor=HexColor("#52606D"),
            spaceBefore=4,
            spaceAfter=10,
        ),
        "quote": ParagraphStyle(
            "GuideQuote",
            parent=body,
            leftIndent=12,
            rightIndent=8,
            borderColor=HexColor(accent),
            borderWidth=1.5,
            borderPadding=7,
            textColor=HexColor("#263B50"),
            spaceBefore=4,
            spaceAfter=8,
        ),
        "small": ParagraphStyle(
            "GuideSmall",
            parent=body,
            fontSize=8,
            leading=10.5,
            textColor=HexColor("#52606D"),
        ),
        "table_cell": ParagraphStyle(
            "GuideTableCell",
            parent=body,
            fontSize=7.4,
            leading=8.8,
            spaceAfter=0,
        ),
        "table_header": ParagraphStyle(
            "GuideTableHeader",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=HexColor("#263B50"),
            spaceAfter=0,
        ),
    }


def _svg_number(element: ET.Element, name: str, default: float = 0.0) -> float:
    raw = element.attrib.get(name)
    if raw is None or raw.endswith("%"):
        return default
    return float(raw)


def _paint(value: Optional[str], fallback: str = "#000000"):
    if value in (None, ""):
        value = fallback
    if value == "none":
        return None
    return HexColor(value)


def svg_drawing(path: Path, max_width: float) -> Drawing:
    """Translate the deterministic renderer's SVG subset into a vector Drawing."""

    root = ET.fromstring(path.read_text(encoding="utf-8"))
    width = float(root.attrib["width"])
    height = float(root.attrib["height"])
    scale = min(max_width / width, 1.0)
    drawing = Drawing(width * scale, height * scale)

    def tx(value: float) -> float:
        return value * scale

    def ty(value: float) -> float:
        return (height - value) * scale

    namespace = "{http://www.w3.org/2000/svg}"
    for element in root.iter():
        tag = element.tag.removeprefix(namespace)
        if tag == "rect":
            raw_width = element.attrib.get("width", "0")
            raw_height = element.attrib.get("height", "0")
            rect_width = width if raw_width.endswith("%") else float(raw_width)
            rect_height = height if raw_height.endswith("%") else float(raw_height)
            x = _svg_number(element, "x")
            y = _svg_number(element, "y")
            shape = Rect(
                tx(x),
                ty(y + rect_height),
                tx(rect_width),
                tx(rect_height),
                rx=tx(_svg_number(element, "rx")),
                ry=tx(_svg_number(element, "rx")),
                fillColor=_paint(element.attrib.get("fill"), "none"),
                strokeColor=_paint(element.attrib.get("stroke"), "none"),
                strokeWidth=tx(_svg_number(element, "stroke-width", 1.0)),
            )
            drawing.add(shape)
        elif tag == "line":
            x1 = _svg_number(element, "x1")
            y1 = _svg_number(element, "y1")
            x2 = _svg_number(element, "x2")
            y2 = _svg_number(element, "y2")
            stroke = _paint(element.attrib.get("stroke"))
            shape = Line(tx(x1), ty(y1), tx(x2), ty(y2))
            shape.strokeColor = stroke
            shape.strokeWidth = tx(_svg_number(element, "stroke-width", 1.0))
            if "stroke-dasharray" in element.attrib:
                shape.strokeDashArray = [
                    tx(float(item))
                    for item in element.attrib["stroke-dasharray"].split()
                ]
            drawing.add(shape)
            if "marker-end" in element.attrib:
                angle = math.atan2(ty(y2) - ty(y1), tx(x2) - tx(x1))
                arrow_length = tx(8)
                arrow_half_width = tx(4)
                end_x, end_y = tx(x2), ty(y2)
                base_x = end_x - arrow_length * math.cos(angle)
                base_y = end_y - arrow_length * math.sin(angle)
                offset_x = arrow_half_width * math.sin(angle)
                offset_y = -arrow_half_width * math.cos(angle)
                drawing.add(
                    Polygon(
                        [
                            end_x,
                            end_y,
                            base_x + offset_x,
                            base_y + offset_y,
                            base_x - offset_x,
                            base_y - offset_y,
                        ],
                        fillColor=stroke,
                        strokeColor=stroke,
                    )
                )
        elif tag == "text":
            anchor = element.attrib.get("text-anchor", "start")
            text_anchor = {
                "middle": "middle",
                "end": "end",
                "start": "start",
            }.get(anchor, "start")
            drawing.add(
                String(
                    tx(_svg_number(element, "x")),
                    ty(_svg_number(element, "y")),
                    _ascii("".join(element.itertext())),
                    fontName="Helvetica",
                    fontSize=tx(_svg_number(element, "font-size", 14.0)),
                    fillColor=_paint(element.attrib.get("fill")),
                    textAnchor=text_anchor,
                )
            )

    return drawing


def _join_markdown_lines(lines: Sequence[str]) -> str:
    return " ".join(line.strip() for line in lines).strip()


def _markdown_table_cells(line: str) -> Optional[list[str]]:
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _is_markdown_table_separator(cells: Optional[Sequence[str]]) -> bool:
    return bool(cells) and all(TABLE_SEPARATOR_CELL.fullmatch(cell) for cell in cells)


def markdown_flowables(
    record: QuestionRecord,
    styles: Mapping[str, ParagraphStyle],
    diagram_width: float,
    body_width: float,
) -> list[Flowable]:
    """Convert the repository's intentionally small Markdown subset."""

    lines = record.markdown.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    flowables: list[Flowable] = []
    diagram_captions = {
        str(diagram["rendered_file"]): str(diagram["caption"])
        for diagram in record.metadata.get("diagrams", [])
    }
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        if line.startswith("```"):
            language = line[3:].strip()
            index += 1
            code_lines: list[str] = []
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(_ascii(lines[index]).replace("\t", "    "))
                index += 1
            if index >= len(lines):
                raise ValueError(f"{record.question_id}: unclosed fenced code block")
            index += 1
            label = f"{language}\n" if language else ""
            flowables.append(
                XPreformatted(
                    html.escape(label + "\n".join(code_lines)),
                    styles["code"],
                )
            )
            continue

        image = IMAGE_LINE.match(line)
        if image:
            alt_text, raw_target = image.groups()
            image_path = (record.package_dir / raw_target).resolve()
            drawing = svg_drawing(image_path, diagram_width)
            caption = diagram_captions.get(image_path.name, alt_text)
            # A diagram always starts a landscape page. Move any immediately
            # preceding heading chain with it so section titles are not left
            # alone on the portrait page before the diagram.
            diagram_headings: list[Flowable] = []
            while (
                flowables
                and isinstance(flowables[-1], Paragraph)
                and flowables[-1].style.name
                in {"GuideH1", "GuideH2", "GuideH3"}
            ):
                diagram_headings.append(flowables.pop())
            diagram_headings.reverse()
            flowables.extend(
                [
                    NextPageTemplate("diagram"),
                    PageBreak(),
                ]
            )
            flowables.append(
                KeepTogether(
                    [
                        Spacer(1, 5 * mm),
                        *diagram_headings,
                        drawing,
                        Paragraph(_inline_markup(caption), styles["caption"]),
                    ]
                )
            )
            flowables.extend(
                [
                    NextPageTemplate("guide"),
                    PageBreak(),
                ]
            )
            index += 1
            continue

        header_cells = _markdown_table_cells(line)
        separator_cells = (
            _markdown_table_cells(lines[index + 1])
            if index + 1 < len(lines)
            else None
        )
        if (
            header_cells is not None
            and _is_markdown_table_separator(separator_cells)
            and len(header_cells) == len(separator_cells)
        ):
            rows = [header_cells]
            index += 2
            while index < len(lines):
                cells = _markdown_table_cells(lines[index])
                if cells is None or len(cells) != len(header_cells):
                    break
                rows.append(cells)
                index += 1

            column_count = len(header_cells)
            if column_count == 2:
                column_widths = [body_width * 0.32, body_width * 0.68]
            else:
                column_widths = [body_width / column_count] * column_count
            table_data = [
                [
                    Paragraph(
                        _inline_markup(cell),
                        styles["table_header" if row_index == 0 else "table_cell"],
                    )
                    for cell in row
                ]
                for row_index, row in enumerate(rows)
            ]
            table = Table(
                table_data,
                colWidths=column_widths,
                repeatRows=1,
                splitByRow=1,
                hAlign="LEFT",
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#E8F0F3")),
                        ("GRID", (0, 0), (-1, -1), 0.35, HexColor("#C8D2DA")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                    ]
                )
            )
            # Short interview tables read as one decision unit. Keeping them
            # together avoids a one-row continuation page that can collide
            # visually with the running header/footer. Larger tables retain
            # normal row splitting.
            flowables.append(KeepTogether([table]) if len(rows) <= 9 else table)
            continue

        heading = HEADING_LINE.match(line)
        if heading:
            level = len(heading.group(1))
            heading_style = styles["h1"] if level == 2 else styles["h2"]
            if level >= 4:
                heading_style = styles["h3"]
            flowables.append(
                Paragraph(_inline_markup(heading.group(2)), heading_style)
            )
            index += 1
            continue

        quote = BLOCKQUOTE_LINE.match(line)
        if quote:
            quote_lines = [quote.group(1)]
            index += 1
            while index < len(lines):
                continuation = BLOCKQUOTE_LINE.match(lines[index])
                if continuation is None:
                    break
                quote_lines.append(continuation.group(1))
                index += 1
            flowables.append(
                Paragraph(
                    _inline_markup(_join_markdown_lines(quote_lines)),
                    styles["quote"],
                )
            )
            continue

        list_match = LIST_LINE.match(line)
        if list_match:
            ordered = list_match.group(2).endswith(".")
            items: list[Paragraph] = []
            while index < len(lines):
                current = LIST_LINE.match(lines[index])
                if current is None:
                    break
                if current.group(2).endswith(".") != ordered:
                    break
                item_lines = [current.group(3)]
                index += 1
                while (
                    index < len(lines)
                    and lines[index].strip()
                    and LIST_LINE.match(lines[index]) is None
                    and HEADING_LINE.match(lines[index]) is None
                    and not lines[index].startswith("```")
                ):
                    item_lines.append(lines[index])
                    index += 1
                items.append(
                    Paragraph(
                        _inline_markup(_join_markdown_lines(item_lines)),
                        styles["bullet"],
                    )
                )
                while index < len(lines) and not lines[index].strip():
                    probe = index + 1
                    if probe < len(lines) and LIST_LINE.match(lines[probe]):
                        index = probe
                        break
                    index += 1
                    break
            list_arguments = {
                "bulletType": "1" if ordered else "bullet",
                "leftIndent": 18,
                "bulletFontName": "Helvetica",
                "bulletFontSize": 8,
                "bulletColor": HexColor("#41566B"),
                "spaceAfter": 6,
            }
            if ordered:
                list_arguments["start"] = "1"
            flowables.append(
                ListFlowable(
                    [ListItem(item) for item in items],
                    **list_arguments,
                )
            )
            continue

        paragraph_lines = [line]
        index += 1
        while (
            index < len(lines)
            and lines[index].strip()
            and not lines[index].startswith("```")
            and HEADING_LINE.match(lines[index]) is None
            and IMAGE_LINE.match(lines[index]) is None
            and LIST_LINE.match(lines[index]) is None
        ):
            paragraph_lines.append(lines[index])
            index += 1
        flowables.append(
            Paragraph(
                _inline_markup(_join_markdown_lines(paragraph_lines)),
                styles["body"],
            )
        )

    return flowables


class GuideDocTemplate(BaseDocTemplate):
    """Document template that registers question headings in the TOC."""

    def __init__(
        self,
        output: Path,
        *,
        guide_title: str,
        version: str,
        build_date: str,
        accent: str,
        preview: bool,
    ) -> None:
        self.guide_title = guide_title
        self.version = version
        self.build_date = build_date
        self.accent = accent
        self.preview = preview
        super().__init__(
            str(output),
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=17 * mm,
            title=guide_title,
            author="C++ Quant Developer Interview Content Factory",
            subject=(
                "Human-reviewed C++ quant developer interview preparation; "
                f"version {version}; build date {build_date}"
            ),
            creator="Deterministic ReportLab publisher",
            invariant=1,
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="body",
        )
        landscape_width, landscape_height = landscape(A4)
        landscape_frame = Frame(
            18 * mm,
            17 * mm,
            landscape_width - 36 * mm,
            landscape_height - 35 * mm,
            id="diagram-body",
        )
        # Frame paddings consume six points on each horizontal edge.
        self.body_width = self.width - 12
        self.diagram_width = landscape_width - 36 * mm - 12
        self.addPageTemplates(
            [
                PageTemplate(
                    id="guide",
                    frames=[frame],
                    onPage=self._draw_page_background,
                    onPageEnd=self._draw_running_furniture,
                ),
                PageTemplate(
                    id="diagram",
                    frames=[landscape_frame],
                    pagesize=landscape(A4),
                    onPage=self._draw_page_background,
                    onPageEnd=self._draw_running_furniture,
                ),
            ]
        )

    def _draw_page_background(self, canvas, document) -> None:
        canvas.saveState()
        canvas.setTitle(self.guide_title)
        canvas.setAuthor("C++ Quant Developer Interview Content Factory")
        canvas.setSubject(
            "C++ quant developer interview guide; "
            f"version {self.version}; build date {self.build_date}"
        )
        canvas.setKeywords(
            f"C++, quant development, interviews, version {self.version}, "
            f"build date {self.build_date}"
        )
        canvas.setCreator("Deterministic ReportLab publisher")
        if document.page == 1:
            page_width, page_height = canvas._pagesize
            canvas.setFillColor(HexColor(self.accent))
            canvas.rect(0, 0, page_width, page_height, fill=1, stroke=0)
        canvas.restoreState()

    def _draw_running_furniture(self, canvas, document) -> None:
        if document.page == 1:
            return
        canvas.saveState()
        page_width, page_height = canvas._pagesize
        canvas.setStrokeColor(HexColor("#D5DEE5"))
        canvas.line(
            18 * mm,
            page_height - 13 * mm,
            page_width - 18 * mm,
            page_height - 13 * mm,
        )
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(HexColor("#667788"))
        canvas.drawString(18 * mm, page_height - 10 * mm, self.guide_title)
        canvas.drawRightString(
            page_width - 18 * mm,
            10 * mm,
            f"{'REVIEW PREVIEW - ' if self.preview else ''}v{self.version} | {document.page}",
        )
        canvas.restoreState()

    def afterFlowable(self, flowable: Flowable) -> None:
        if isinstance(flowable, Paragraph) and flowable.style.name == "QuestionTitle":
            anchor = getattr(flowable, "_question_anchor", None)
            title = getattr(flowable, "_question_title", flowable.getPlainText())
            if anchor:
                self.canv.bookmarkPage(anchor)
                self.canv.addOutlineEntry(title, anchor, level=0, closed=False)
                self.notify("TOCEntry", (0, title, self.page, anchor))


def _cover_story(
    title: str,
    styles: Mapping[str, ParagraphStyle],
    *,
    version: str,
    build_date: str,
    question_count: int,
    preview: bool,
) -> list[Flowable]:
    edition = "Internal review preview" if preview else "Approved edition"
    return [
        Spacer(1, 36 * mm),
        Paragraph(_inline_markup(title), styles["cover_title"]),
        Paragraph(
            f"{edition}<br/>Version {html.escape(version)}",
            styles["cover_subtitle"],
        ),
        Spacer(1, 55 * mm),
        Paragraph(
            (
                f"Build date: {html.escape(build_date)}<br/>"
                f"Questions: {question_count}<br/><br/>"
                + (
                    "This preview may contain material awaiting human approval."
                    if preview
                    else "Only human-approved or previously published questions are included."
                )
            ),
            styles["cover_subtitle"],
        ),
        PageBreak(),
    ]


def _toc_story(
    styles: Mapping[str, ParagraphStyle],
    *,
    has_questions: bool,
) -> list[Flowable]:
    story: list[Flowable] = [
        Paragraph("Contents", styles["h1"]),
        Spacer(1, 3 * mm),
    ]
    if has_questions:
        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle(
                "TOCQuestion",
                parent=styles["body"],
                fontSize=9.5,
                leading=14,
                leftIndent=0,
                firstLineIndent=0,
                textColor=HexColor("#263B50"),
            )
        ]
        story.extend([toc, PageBreak()])
    else:
        story.extend(
            [
                Paragraph(
                    "No questions currently satisfy the publication gate.",
                    styles["body"],
                ),
                PageBreak(),
            ]
        )
    return story


def _catalog_story(
    records: Sequence[QuestionRecord],
    styles: Mapping[str, ParagraphStyle],
    accent: str,
) -> list[Flowable]:
    categories = category_counts(records)
    difficulties = difficulty_counts(records)
    story: list[Flowable] = [
        Paragraph("Question catalog", styles["h1"]),
        Paragraph(
            (
                f"{len(records)} question{'s' if len(records) != 1 else ''}. "
                "Counts are generated directly from metadata."
            ),
            styles["body"],
        ),
        Paragraph("Category counts", styles["h2"]),
    ]

    category_rows = [["Category", "Questions"]]
    if categories:
        category_rows.extend(
            [category.replace("-", " ").title(), str(count)]
            for category, count in sorted(categories.items())
        )
    else:
        category_rows.append(["No approved questions", "0"])
    category_table = Table(category_rows, colWidths=[120 * mm, 32 * mm], repeatRows=1)
    category_table.setStyle(_table_style(accent))
    story.extend([category_table, Spacer(1, 4 * mm)])

    difficulty_rows = [["Difficulty", "Questions"]]
    difficulty_rows.extend(
        [str(level), str(difficulties.get(level, 0))] for level in range(1, 6)
    )
    difficulty_table = Table(
        difficulty_rows, colWidths=[120 * mm, 32 * mm], repeatRows=1
    )
    difficulty_table.setStyle(_table_style(accent))
    story.extend([Paragraph("Difficulty counts", styles["h2"]), difficulty_table])

    if records:
        by_category: dict[str, list[QuestionRecord]] = defaultdict(list)
        for record in records:
            by_category[record.primary_category].append(record)
        story.append(Paragraph("Questions", styles["h2"]))
        for category, items in sorted(by_category.items()):
            story.append(
                Paragraph(category.replace("-", " ").title(), styles["h3"])
            )
            for record in items:
                label = (
                    f'<link href="#{question_anchor(record.question_id)}" '
                    f'color="{accent}">{html.escape(_ascii(record.title))}</link>'
                    f" - difficulty {record.metadata['difficulty']}, "
                    f"{record.metadata['expected_duration_minutes']} minutes"
                )
                story.append(Paragraph(label, styles["body"]))
    else:
        story.extend(
            [
                Spacer(1, 5 * mm),
                Paragraph(
                    (
                        "No content has been promoted to <font name=\"Courier\">"
                        "approved</font> or <font name=\"Courier\">published</font>. "
                        "The guide is intentionally empty rather than leaking "
                        "review-only material."
                    ),
                    styles["meta"],
                ),
            ]
        )
    story.append(PageBreak())
    return story


def _table_style(accent: str) -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), HexColor(accent)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#C8D2DA")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F3F6F8")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )


def build_pdf(
    question_type: str,
    records: Sequence[QuestionRecord],
    output: Path,
    *,
    root: Path = ROOT,
    preview: bool = False,
) -> Path:
    spec = GUIDE_SPECS[question_type]
    accent = GUIDE_COLORS[question_type]
    styles = _styles(accent)
    version = load_project_version(root)
    build_date = _build_date()

    output.parent.mkdir(parents=True, exist_ok=True)
    document = GuideDocTemplate(
        output,
        guide_title=spec["title"],
        version=version,
        build_date=build_date,
        accent=accent,
        preview=preview,
    )

    story: list[Flowable] = []
    story.extend(
        _cover_story(
            spec["title"],
            styles,
            version=version,
            build_date=build_date,
            question_count=len(records),
            preview=preview,
        )
    )
    story.extend(_toc_story(styles, has_questions=bool(records)))
    story.extend(_catalog_story(records, styles, accent))

    for record_index, record in enumerate(records):
        title = Paragraph(
            (
                f'<a name="{question_anchor(record.question_id)}"/>'
                f"{html.escape(_ascii(record.title))}"
            ),
            styles["question"],
        )
        title._question_anchor = question_anchor(record.question_id)
        title._question_title = _ascii(record.title)
        story.extend(
            [
                title,
                Paragraph(
                    (
                        f"<font name=\"Courier\">{record.question_id}</font> | "
                        f"difficulty {record.metadata['difficulty']} | "
                        f"{record.metadata['expected_duration_minutes']} minutes | "
                        f"status: <font name=\"Courier\">"
                        f"{record.metadata['status']}</font>"
                    ),
                    styles["meta"],
                ),
            ]
        )
        story.extend(
            markdown_flowables(
                record,
                styles,
                document.diagram_width,
                document.body_width,
            )
        )
        if record_index != len(records) - 1:
            story.append(PageBreak())

    document.multiBuild(story)
    return output


def _build_date() -> str:
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch is not None:
        return dt.datetime.fromtimestamp(
            int(source_date_epoch), tz=dt.timezone.utc
        ).date().isoformat()
    return dt.datetime.now(tz=dt.timezone.utc).date().isoformat()


def build_all_pdfs(
    root: Path = ROOT,
    *,
    review_preview: bool = False,
) -> list[Path]:
    root = root.resolve()
    records = discover_questions(root)
    if not review_preview:
        records = [record for record in records if is_publication_ready(record)]
    grouped = questions_by_type(records, root)
    output_root = (
        root / "generated" / "pdf-preview" if review_preview else root / "dist"
    )

    outputs = []
    for question_type, spec in GUIDE_SPECS.items():
        output = output_root / spec["pdf"]
        outputs.append(
            build_pdf(
                question_type,
                grouped[question_type],
                output,
                root=root,
                preview=review_preview,
            )
        )
    return outputs


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--review-preview",
        action="store_true",
        help="build an internal preview containing non-private review content",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    for output in build_all_pdfs(args.root, review_preview=args.review_preview):
        print(f"built {output.relative_to(args.root.resolve())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
