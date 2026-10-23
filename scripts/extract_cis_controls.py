"""Extract the CIS Controls framework from the published workbook into JSON.

Usage: python scripts/extract_cis_controls.py <CIS_Controls.xlsx> <out.json>

The sheet lists one row per control (no safeguard number) followed by its safeguards.
Implementation Groups are marked with an "x" and are cumulative: IG1 ⊂ IG2 ⊂ IG3.

Safeguard numbers are stored as floats, so 3.10 and 3.1 are the same cell value. The
numbers are rebuilt from each safeguard's position inside its control and checked
against the cell, which is what that collision would otherwise silently cost: five
safeguards (3.10, 4.10, 8.10, 13.10, 16.10) overwriting their siblings.
"""

import json
import sys

import openpyxl

COLUMNS = ("control", "safeguard", "asset_class", "security_function", "title", "description")


def _is_truncated(raw: float, control: str, position: int) -> bool:
    """True when the cell holds x.10, x.20 … which a float renders as x.1, x.2."""
    if position % 10:
        return False
    return abs(float(raw) - float(f"{control}.{position // 10}")) < 1e-9


def clean(value) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def main(src: str, dst: str) -> None:
    wb = openpyxl.load_workbook(src, data_only=True)
    sheet = wb.worksheets[0]
    version = sheet.title.replace("Controls", "").strip() or "v8.1.2"

    controls: list[dict] = []
    by_number: dict[str, dict] = {}
    safeguard_count = 0

    for row in sheet.iter_rows(min_row=2, values_only=True):
        values = dict(zip(COLUMNS, row[:6]))
        igs = [bool(clean(cell)) for cell in row[6:9]]
        number = clean(values["control"])
        if number is None:
            continue

        if clean(values["safeguard"]) is None:
            control = {
                "number": number,
                "title": clean(values["title"]),
                "description": clean(values["description"]),
                "safeguards": [],
            }
            controls.append(control)
            by_number[number] = control
            continue

        parent = by_number.get(number)
        if parent is None:
            raise ValueError(f"safeguard {values['safeguard']} has no control {number}")

        position = len(parent["safeguards"]) + 1
        safeguard_id = f"{number}.{position}"
        raw = values["safeguard"]
        if isinstance(raw, (int, float)):
            # A float cell can only disagree with the position when a number was
            # truncated (x.10 -> x.1); anything else means the rows are out of order.
            if abs(float(raw) - float(safeguard_id)) > 1e-9 and not _is_truncated(raw, number, position):
                raise ValueError(f"expected safeguard {safeguard_id}, sheet says {raw}")
        elif clean(raw) not in (safeguard_id, None):
            raise ValueError(f"expected safeguard {safeguard_id}, sheet says {clean(raw)}")

        parent["safeguards"].append(
            {
                "id": safeguard_id,
                "title": clean(values["title"]),
                "description": clean(values["description"]),
                "asset_class": clean(values["asset_class"]),
                "security_function": clean(values["security_function"]),
                # The lowest group a safeguard belongs to; groups are cumulative.
                "ig": 1 if igs[0] else 2 if igs[1] else 3,
            }
        )
        safeguard_count += 1

    asset_classes = sorted({s["asset_class"] for c in controls for s in c["safeguards"] if s["asset_class"]})
    functions = sorted({s["security_function"] for c in controls for s in c["safeguards"] if s["security_function"]})

    template = {
        "framework": "cis",
        "version": version,
        "title": f"CIS Controls {version}",
        "source": "Center for Internet Security, CIS Critical Security Controls",
        "asset_classes": asset_classes,
        "security_functions": functions,
        "implementation_groups": [
            {"level": 1, "title": "IG1", "description": "Базовая кибергигиена: минимум, обязательный для любой организации"},
            {"level": 2, "title": "IG2", "description": "Организации, управляющие ИТ для нескольких подразделений с разным риском"},
            {"level": 3, "title": "IG3", "description": "Организации с выделенной функцией ИБ и чувствительными активами"},
        ],
        "controls": controls,
    }
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(template, fh, ensure_ascii=False, indent=2)
    print(f"wrote {dst}: {len(controls)} controls, {safeguard_count} safeguards")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
