"""Extract the BIA questionnaire template from the source Excel workbook into JSON.

Usage: python scripts/extract_questionnaire.py <workbook.xlsx> <out.json>

The layout of the workbook ("Опросник" + "Списки" sheets) is hard-coded below: it is a
fixed template, and the row ranges are the contract between the workbook and the seed.
"""

import json
import sys

import openpyxl

LEVELS = ["Крайне высокий", "Высокий", "Средний", "Низкий"]
LEVEL_SCORES = {"Низкий": 0.25, "Средний": 0.5, "Высокий": 0.75, "Крайне высокий": 1.0}

# Matrix blocks: (part, damage_type, header_row, description_row, first_q_row, last_q_row)
AVAILABILITY_BLOCKS = [
    ("financial", 28, 29, 30, 36),
    ("regulatory", 37, 38, 39, 45),
    ("operational", 46, 47, 56, 62),
    ("reputational", 63, 64, 65, 71),
]
INTEGRITY_BLOCKS = [
    ("financial", 73, 74, 75, 81),
    ("regulatory", 82, 83, 84, 90),
    ("operational", 91, 92, 93, 99),
    ("reputational", 100, 101, 102, 108),
]
# Operational damage is described per functional area (rows 47..55) instead of one row.
OPERATIONAL_AREA_ROWS = range(47, 56)

AVAILABILITY_PERIODS = [
    ("30 мин", 0.5, 0.30),
    ("1 час", 1, 0.25),
    ("8 часов (рабочий день)", 8, 0.20),
    ("24 часа", 24, 0.12),
    ("3 суток", 72, 0.07),
    ("2 недели", 336, 0.04),
    ("месяц", 720, 0.02),
]
INTEGRITY_PERIODS = [
    ("2 минуты", 2 / 60, 0.30),
    ("2 часа", 2, 0.25),
    ("8 часов (рабочий день)", 8, 0.20),
    ("24 часа", 24, 0.12),
    ("3 суток", 72, 0.07),
    ("7 суток", 168, 0.04),
    ("2 недели", 336, 0.02),
]

# Plain questions: row -> (code, answer kind, list column in "Списки", options count)
LIST_COLUMNS = {
    "functional_area": 1,
    "daily_users": 2,
    "seasonality": 3,
    "manual_workaround": 4,
    "alt_data_source": 5,
    "yes_partial_no": 6,
    "rto_scale": 7,
    "rpo_scale": 8,
}
PLAIN_QUESTIONS = {
    7: ("text", None),
    8: ("text", None),
    9: ("multiselect3", "functional_area"),
    10: ("textarea", None),
    11: ("textarea", None),
    12: ("textarea", None),
    13: ("textarea", None),
    14: ("select", "daily_users"),
    15: ("select", "seasonality"),
    16: ("select", "manual_workaround"),
    17: ("textarea", None),
    18: ("select", "alt_data_source"),
    19: ("textarea", None),
    20: ("textarea", None),
    21: ("textarea", None),
    23: ("select_text", "yes_partial_no"),
    24: ("select_text", "yes_partial_no"),
    25: ("select_text", "yes_partial_no"),
    26: ("select_text", "yes_partial_no"),
    110: ("select", "rto_scale"),
    111: ("select", "rto_scale"),
    112: ("select", "rpo_scale"),
    114: ("select", "rto_scale"),
    115: ("select", "rpo_scale"),
}
OPTIONAL_QUESTIONS = {5, 6, 7, 13, 14, 15, 79, 80}
PART_ROWS = {6: 1, 22: 2, 27: 3, 72: 4, 109: 5, 113: 6}


def clean(value):
    if value is None:
        return None
    return str(value).strip() or None


def main(src, dst):
    wb = openpyxl.load_workbook(src, data_only=True)
    q = wb["Опросник"]
    lists = wb["Списки"]

    option_lists = {}
    for name, col in LIST_COLUMNS.items():
        values = [clean(lists.cell(row=r, column=col).value) for r in range(1, 12)]
        option_lists[name] = [v for v in values if v]

    parts = []
    for row, number in sorted(PART_ROWS.items()):
        parts.append({"number": number, "title": clean(q.cell(row=row, column=1).value)})

    questions = []
    for row, (kind, list_name) in sorted(PLAIN_QUESTIONS.items()):
        code = q.cell(row=row, column=1).value
        questions.append(
            {
                "code": int(code),
                "part": max(n for r, n in PART_ROWS.items() if r < row),
                "row": row,
                "kind": kind,
                "text": clean(q.cell(row=row, column=2).value),
                "help": clean(q.cell(row=row, column=3).value),
                "option_list": list_name,
                "required": int(code) not in OPTIONAL_QUESTIONS,
            }
        )

    def block(part, damage_type, header_row, desc_row, first_row, last_row, periods):
        prompt = clean(q.cell(row=header_row, column=1).value)
        if damage_type == "operational":
            descriptions = [
                {
                    "area": clean(q.cell(row=r, column=1).value),
                    "levels": {
                        level: clean(q.cell(row=r, column=4 + i).value)
                        for i, level in enumerate(LEVELS)
                    },
                }
                for r in OPERATIONAL_AREA_ROWS
            ]
        else:
            descriptions = [
                {
                    "area": None,
                    "levels": {
                        level: clean(q.cell(row=desc_row, column=4 + i).value)
                        for i, level in enumerate(LEVELS)
                    },
                }
            ]
        rows = []
        for offset, row in enumerate(range(first_row, last_row + 1)):
            label, hours, weight = periods[offset]
            rows.append(
                {
                    "code": int(q.cell(row=row, column=1).value),
                    "row": row,
                    "label": clean(q.cell(row=row, column=2).value) or label,
                    "period_label": label,
                    "period_hours": hours,
                    "weight": weight,
                }
            )
        return {
            "part": part,
            "damage_type": damage_type,
            "prompt": prompt,
            "descriptions": descriptions,
            "rows": rows,
        }

    matrices = [
        block(3, dt, h, d, f, l, AVAILABILITY_PERIODS) for dt, h, d, f, l in AVAILABILITY_BLOCKS
    ] + [block(4, dt, h, d, f, l, INTEGRITY_PERIODS) for dt, h, d, f, l in INTEGRITY_BLOCKS]

    instructions = [
        clean(c.value) for c in wb["ИНСТРУКЦИЯ"]["A"] if clean(c.value)
    ]

    template = {
        "title": clean(q.cell(row=1, column=1).value),
        "notes": clean(q.cell(row=2, column=1).value),
        "instructions": instructions,
        "levels": LEVELS,
        "level_scores": LEVEL_SCORES,
        "option_lists": option_lists,
        "parts": parts,
        "questions": questions,
        "matrices": matrices,
        "calculation_notes": clean(wb["Расчет"]["C17"].value),
    }
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(template, fh, ensure_ascii=False, indent=2)
    print(f"wrote {dst}: {len(questions)} questions, {len(matrices)} matrices")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
