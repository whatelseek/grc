"""The workbook's «Проверка» column, reproduced server-side."""

from app.models import Answer
from app.scoring import LEVEL_ORDER
from app.template import load_template, matrix_rows, plain_questions, required_codes


def _has_value(answer: Answer | None) -> bool:
    if answer is None:
        return False
    if answer.level:
        return True
    if answer.selections:
        return True
    return bool((answer.text or "").strip())


def check(answers: dict[int, Answer], version: str = "v1") -> dict:
    """Return per-question issues plus the progress counter shown at the top of the sheet."""
    issues: list[dict] = []
    plain = plain_questions(version)
    grid = matrix_rows(version)

    for code in required_codes(version):
        if not _has_value(answers.get(code)):
            issues.append(
                {
                    "code": code,
                    "severity": "missing",
                    "message": "← отметьте уровень ущерба" if code in grid else "← заполните",
                }
            )

    # Part 1 question 3 wants between one and three functional areas.
    area_answer = answers.get(3)
    if area_answer is not None and area_answer.selections is not None:
        if len(area_answer.selections) > 3:
            issues.append(
                {"code": 3, "severity": "warning", "message": "⚠ укажите не более трёх областей"}
            )

    # Monotonicity: a longer outage/data-loss window may not carry a softer damage level.
    for matrix in load_template(version)["matrices"]:
        worst_so_far = -1
        worst_label = None
        for row in matrix["rows"]:
            answer = answers.get(row["code"])
            level = answer.level if answer else None
            if not level:
                continue
            rank = LEVEL_ORDER.index(level)
            if rank < worst_so_far:
                issues.append(
                    {
                        "code": row["code"],
                        "severity": "warning",
                        "message": (
                            f"⚠ на более длинном сроке уровень мягче, чем «{worst_label}» "
                            "на коротком — проверьте или поясните в вопросе 15"
                        ),
                    }
                )
            else:
                worst_so_far = rank
                worst_label = level

    required = required_codes(version)
    filled = sum(1 for code in required if _has_value(answers.get(code)))
    warnings = sum(1 for issue in issues if issue["severity"] == "warning")
    return {
        "issues": issues,
        "progress": {
            "required_total": len(required),
            "required_filled": filled,
            "optional_total": len(plain) + len(grid) - len(required),
            "warnings": warnings,
            "complete": filled == len(required) and warnings == 0,
        },
    }
