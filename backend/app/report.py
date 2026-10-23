"""The audit report a consultant sends to the client.

Produced as .docx on purpose: the consultant edits the wording before sending, which a
PDF would not allow. Colours and type follow the brand template used by the interface.
"""

import io
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from app.models import Assessment

NAVY = RGBColor(0x0F, 0x3C, 0x64)
INK = RGBColor(0x00, 0x00, 0x00)
GREY = RGBColor(0x4D, 0x4D, 0x4D)
TEAL = RGBColor(0x09, 0x6D, 0x68)
TERRACOTTA = RGBColor(0x9A, 0x39, 0x0D)
BURGUNDY = RGBColor(0x50, 0x00, 0x05)

FONT = "Source Sans Pro"
LOGO = Path(__file__).parent / "data" / "report-logo.png"

STATUS_LABELS = {
    "not_implemented": "Не внедрено",
    "partial": "Частично",
    "implemented": "Внедрено",
    "not_applicable": "Не применимо",
}
PRIORITY_LABELS = {"high": "Высокий", "medium": "Средний", "low": "Низкий"}
FUNCTION_LABELS = {
    "Govern": "Govern · управление",
    "Identify": "Identify · учёт",
    "Protect": "Protect · защита",
    "Detect": "Detect · обнаружение",
    "Respond": "Respond · реагирование",
    "Recover": "Recover · восстановление",
}


def percent(value: float | None) -> str:
    return "—" if value is None else f"{round(value * 100)}%"


def _shade(cell, hex_fill: str) -> None:
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")  # «solid» renders as black
    shading.set(qn("w:fill"), hex_fill)
    cell._tc.get_or_add_tcPr().append(shading)


def _hairline_borders(table) -> None:
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")  # quarter-points: a hairline
        element.set(qn("w:color"), "D0D0D0")
        borders.append(element)
    table._tbl.tblPr.append(borders)


def _text(paragraph, text: str, *, size=10, bold=False, color=INK, italic=False):
    run = paragraph.add_run(text)
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return run


def _heading(document, text: str, level: int = 1):
    paragraph = document.add_heading(level=level)
    _text(paragraph, text, size=16 if level == 1 else 13, bold=True, color=NAVY)
    return paragraph


TWIPS_PER_CM = 567


def _fix_columns(table, widths: list[float]) -> None:
    """Pin the column grid.

    A fixed-layout table is laid out from w:tblGrid, not from the cell widths, and
    python-docx writes an even grid — so without this every column comes out the same
    width and long text is squeezed into a sliver.
    """
    table.autofit = False
    properties = table._tbl.tblPr

    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    properties.append(layout)

    total = OxmlElement("w:tblW")
    total.set(qn("w:type"), "dxa")
    total.set(qn("w:w"), str(int(sum(widths) * TWIPS_PER_CM)))
    properties.append(total)

    grid = table._tbl.find(qn("w:tblGrid"))
    for column in list(grid):
        grid.remove(column)
    for width in widths:
        column = OxmlElement("w:gridCol")
        column.set(qn("w:w"), str(int(width * TWIPS_PER_CM)))
        grid.append(column)


def _table(document, headers: list[str], widths: list[float]):
    table = document.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    _fix_columns(table, widths)
    _hairline_borders(table)
    for index, (header, width) in enumerate(zip(headers, widths)):
        cell = table.rows[0].cells[index]
        cell.width = Cm(width)
        _shade(cell, "ECECEC")
        cell.paragraphs[0].text = ""
        _text(cell.paragraphs[0], header, size=9, bold=True, color=GREY)
    return table


def _row(table, values: list[str], widths: list[float], colors: list[RGBColor | None] | None = None):
    cells = table.add_row().cells
    for index, (value, width) in enumerate(zip(values, widths)):
        # Width is per cell and must be repeated on every row for a fixed layout.
        cells[index].width = Cm(width)
        cells[index].paragraphs[0].text = ""
        color = (colors or [None] * len(values))[index] or INK
        _text(cells[index].paragraphs[0], value, size=9, color=color)
    return cells


def _status_color(status: str) -> RGBColor:
    return {
        "implemented": TEAL,
        "partial": TERRACOTTA,
        "not_implemented": BURGUNDY,
    }.get(status, GREY)


def build(
    assessment: Assessment,
    result: dict,
    catalogue: dict[str, dict],
    *,
    comparison: dict | None = None,
    recovery: list[dict] | None = None,
) -> bytes:
    """Return the .docx bytes. `comparison` and `recovery` are included when available."""
    document = Document()
    style = document.styles["Normal"]
    style.font.name = FONT
    style.font.size = Pt(10)

    section = document.sections[0]
    section.left_margin = section.right_margin = Cm(2)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(1.8)
    content_width = (section.page_width - section.left_margin - section.right_margin) / 360000

    # Title block
    if LOGO.exists():
        document.add_picture(str(LOGO), width=Cm(3.4))
    _heading(document, "Аудит мер защиты", level=1)
    subtitle = document.add_paragraph()
    _text(subtitle, f"{assessment.client.name}", size=13, bold=True)
    meta = document.add_paragraph()
    _text(
        meta,
        f"{assessment.catalogue.title if assessment.catalogue else assessment.framework} · "
        f"версия каталога {assessment.framework_version} · целевая группа IG{assessment.target_ig}",
        size=10,
        color=GREY,
    )
    stamp = document.add_paragraph()
    _text(stamp, f"Дата отчёта: {date.today().strftime('%d.%m.%Y')}", size=10, color=GREY)
    if assessment.assessor is not None:
        _text(
            stamp,
            f"   ·   Аудитор: {assessment.assessor.full_name or assessment.assessor.email}",
            size=10,
            color=GREY,
        )

    # Summary
    _heading(document, "Итог", level=2)
    overall = result["overall"]
    groups = result["implementation_groups"]
    ig1_gaps = sum(1 for gap in result["gaps"] if gap["ig"] == 1)
    summary = document.add_paragraph()
    _text(
        summary,
        f"Из {overall['in_scope']} требований в объёме IG{assessment.target_ig} "
        f"внедрено полностью {overall['implemented']}, частично {overall['partial']}, "
        f"не внедрено {overall['not_implemented']}"
        + (f", признано неприменимыми {overall['not_applicable']}" if overall["not_applicable"] else "")
        + f". Общая реализация — {percent(overall['implementation'])}.",
        size=10,
    )
    verdict = document.add_paragraph()
    _text(
        verdict,
        f"Требуют работы {len(result['gaps'])} мер, из них {ig1_gaps} относятся к IG1 — "
        "базовой кибергигиене, с которой начинают.",
        size=10,
        bold=True,
        color=BURGUNDY if ig1_gaps else TEAL,
    )

    widths = [content_width * share for share in (0.34, 0.22, 0.22, 0.22)]
    table = _table(document, ["Группа", "Реализация", "Требований в объёме", "Не внедрено"], widths)
    for name in ("IG1", "IG2", "IG3"):
        group = groups[name]
        _row(
            table,
            [
                f"{name}{' — цель' if group['level'] == assessment.target_ig else ''}",
                percent(group["implementation"]),
                str(group["in_scope"]),
                str(group["not_implemented"]),
            ],
            widths,
        )

    # Dynamics
    if comparison is not None:
        _heading(document, "Динамика с прошлого аудита", level=2)
        delta = comparison["overall_delta"]
        line = document.add_paragraph()
        _text(
            line,
            f"«{comparison['base']['name']}»: {percent(comparison['base']['implementation'])} → "
            f"«{comparison['target']['name']}»: {percent(comparison['target']['implementation'])}"
            f" ({'+' if (delta or 0) >= 0 else ''}{round((delta or 0) * 100)} п.п.). "
            f"Улучшено требований: {len(comparison['improved'])}, "
            f"откатилось: {len(comparison['regressed'])}.",
            size=10,
            color=TEAL if (delta or 0) >= 0 else TERRACOTTA,
        )
        if comparison["regressed"]:
            _text(
                document.add_paragraph(),
                "Откаты назад требуют объяснения — ниже перечислены требования, "
                "по которым статус ухудшился:",
                size=10,
            )
            back_widths = [content_width * share for share in (0.11, 0.57, 0.16, 0.16)]
            back = _table(document, ["Требование", "Что это", "Было", "Стало"], back_widths)
            for row in comparison["regressed"][:15]:
                _row(
                    back,
                    [
                        row["safeguard_id"],
                        row["title"],
                        STATUS_LABELS.get(row["before"], row["before"]),
                        STATUS_LABELS.get(row["after"], row["after"]),
                    ],
                    back_widths,
                )

    # By control
    _heading(document, "Реализация по контролям", level=2)
    control_widths = [content_width * share for share in (0.08, 0.52, 0.16, 0.24)]
    controls = _table(
        document, ["№", "Контроль", "Реализация", "Не внедрено / частично"], control_widths
    )
    titles = {meta["control"]: meta["control_title"] for meta in catalogue.values()}
    for row in result["by_control"]:
        _row(
            controls,
            [
                row["control"],
                titles.get(row["control"], ""),
                percent(row["implementation"]),
                f"{row['not_implemented']} / {row['partial']}",
            ],
            control_widths,
        )

    # By security function
    _heading(document, "Реализация по функциям", level=2)
    function_widths = [content_width * share for share in (0.46, 0.18, 0.18, 0.18)]
    functions = _table(
        document, ["Функция", "Реализация", "В объёме", "Не внедрено"], function_widths
    )
    for row in result["by_function"]:
        _row(
            functions,
            [
                FUNCTION_LABELS.get(row["security_function"], row["security_function"]),
                percent(row["implementation"]),
                str(row["in_scope"]),
                str(row["not_implemented"]),
            ],
            function_widths,
        )

    # Remediation plan
    document.add_page_break()
    _heading(document, "План устранения", level=2)
    _text(
        document.add_paragraph(),
        "Порядок — от IG1 к старшим группам, внутри группы по приоритету.",
        size=10,
        color=GREY,
    )
    gap_widths = [content_width * share for share in (0.07, 0.36, 0.06, 0.12, 0.13, 0.16, 0.10)]
    gaps_table = _table(
        document,
        ["Мера", "Что сделать", "IG", "Статус", "Приоритет", "Ответственный", "Срок"],
        gap_widths,
    )
    for gap in result["gaps"]:
        _row(
            gaps_table,
            [
                gap["safeguard_id"],
                gap["title"],
                f"IG{gap['ig']}",
                STATUS_LABELS.get(gap["status"], gap["status"]),
                PRIORITY_LABELS.get(gap["priority"] or "", "—"),
                gap["owner"] or "не назначен",
                gap["due_date"] or "не задан",
            ],
            gap_widths,
            colors=[None, None, None, _status_color(gap["status"]), None, None, None],
        )
    if not result["gaps"]:
        _text(
            document.add_paragraph(),
            f"Все требования в объёме IG{assessment.target_ig} внедрены.",
            size=10,
            color=TEAL,
        )

    # Link to the BIA side
    if recovery:
        _heading(document, "Связь с оценкой влияния (BIA)", level=2)
        _text(
            document.add_paragraph(),
            "Сроки восстановления, рассчитанные по опросникам BIA, обеспечиваются мерами "
            "контролей 11 (Data Recovery) и 17 (Incident Response). Ниже — системы, которые "
            "сейчас не укладываются в расчётный objective.",
            size=10,
        )
        recovery_widths = [content_width * share for share in (0.34, 0.22, 0.22, 0.22)]
        recovery_table = _table(
            document, ["Система", "Нужно (RTO)", "Сейчас", "Отставание"], recovery_widths
        )
        for row in recovery:
            _row(
                recovery_table,
                [row["system"], row["required"], row["current"], row["gap"]],
                recovery_widths,
                colors=[None, None, None, TERRACOTTA],
            )

    # Appendix
    document.add_page_break()
    _heading(document, "Приложение. Все требования в объёме", level=2)
    appendix_widths = [content_width * share for share in (0.09, 0.57, 0.07, 0.15, 0.12)]
    appendix = _table(
        document, ["Мера", "Требование", "Группа", "Статус", "Доказательства"], appendix_widths
    )
    verdicts = {item.safeguard_id: item for item in assessment.items}
    for code, meta in sorted(
        catalogue.items(), key=lambda pair: tuple(int(p) for p in pair[0].split("."))
    ):
        if meta["ig"] > assessment.target_ig:
            continue
        item = verdicts.get(code)
        status = item.status.value if item else "not_implemented"
        _row(
            appendix,
            [
                code,
                meta["title"],
                f"IG{meta['ig']}",
                STATUS_LABELS.get(status, status),
                str(len(item.evidence)) if item and item.evidence else "—",
            ],
            appendix_widths,
            colors=[None, None, None, _status_color(status), None],
        )

    footer = document.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _text(
        footer,
        "Отчёт сформирован автоматически по данным оценки. "
        "Формулировки требований приведены по каталогу "
        f"{assessment.framework_version}.",
        size=8,
        color=GREY,
        italic=True,
    )

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
