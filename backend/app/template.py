"""Access to the questionnaire template extracted from the source workbook."""

import json
from functools import lru_cache
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "data"
DEFAULT_VERSION = "v1"


@lru_cache
def load_template(version: str = DEFAULT_VERSION) -> dict:
    path = TEMPLATE_DIR / f"questionnaire_{version}.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache
def matrix_rows(version: str = DEFAULT_VERSION) -> dict[int, dict]:
    """question_code -> {part, damage_type, period_hours, weight, ...} for every X-grid row."""
    out: dict[int, dict] = {}
    for matrix in load_template(version)["matrices"]:
        for row in matrix["rows"]:
            out[row["code"]] = {
                "part": matrix["part"],
                "damage_type": matrix["damage_type"],
                "label": row["label"],
                "period_label": row["period_label"],
                "period_hours": row["period_hours"],
                "weight": row["weight"],
            }
    return out


@lru_cache
def plain_questions(version: str = DEFAULT_VERSION) -> dict[int, dict]:
    return {q["code"]: q for q in load_template(version)["questions"]}


@lru_cache
def required_codes(version: str = DEFAULT_VERSION) -> tuple[int, ...]:
    codes = [q["code"] for q in load_template(version)["questions"] if q["required"]]
    codes += list(matrix_rows(version))
    return tuple(sorted(codes))
