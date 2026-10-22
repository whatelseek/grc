"""BIA scoring, ported from the workbook's «Расчет» sheet.

Rules (sheet note «Пояснения к расчетам»):
 1. Qualitative damage levels become scores: Низкий 25%, Средний 50%, Высокий 75%,
    Крайне высокий 100%.
 2. Scores are multiplied by the weight of their period.
 3. Criticality for availability (part 3) / integrity (part 4) is the weighted sum over all
    periods, computed per damage type.
 4. Overall criticality is the maximum over the eight series (4 damage types x 2 parts).
 5. MTPD is the shortest downtime period that reaches «Крайне высокий».
 6. RTO is the minimum of: the shortest period reaching «Средний», half the shortest period
    reaching «Высокий», a third of the shortest period reaching «Крайне высокий».
 7. RPO uses the same rule as RTO over the data-loss periods of part 4.
"""

from dataclasses import dataclass, field

from app.template import load_template, matrix_rows

LEVEL_SCORES = {"Низкий": 0.25, "Средний": 0.5, "Высокий": 0.75, "Крайне высокий": 1.0}
LEVEL_ORDER = ["Низкий", "Средний", "Высокий", "Крайне высокий"]
AVAILABILITY_PART = 3
INTEGRITY_PART = 4


@dataclass
class SeriesScore:
    damage_type: str
    part: int
    criticality: float
    answered: int
    total: int
    detail: list[dict] = field(default_factory=list)


def _series(answers: dict[int, str | None], version: str) -> dict[tuple[int, str], SeriesScore]:
    out: dict[tuple[int, str], SeriesScore] = {}
    for matrix in load_template(version)["matrices"]:
        key = (matrix["part"], matrix["damage_type"])
        total = 0.0
        answered = 0
        detail = []
        for row in matrix["rows"]:
            level = answers.get(row["code"])
            score = LEVEL_SCORES.get(level or "")
            if score is not None:
                total += score * row["weight"]
                answered += 1
            detail.append(
                {
                    "code": row["code"],
                    "period_label": row["period_label"],
                    "period_hours": row["period_hours"],
                    "weight": row["weight"],
                    "level": level,
                    "weighted_score": None if score is None else round(score * row["weight"], 4),
                }
            )
        out[key] = SeriesScore(
            damage_type=matrix["damage_type"],
            part=matrix["part"],
            criticality=round(total, 4),
            answered=answered,
            total=len(matrix["rows"]),
            detail=detail,
        )
    return out


def _shortest_period_at(answers: dict[int, str | None], part: int, level: str, version: str) -> float | None:
    """Shortest period (in hours) at which `level` is reported, over every damage type."""
    candidates = [
        meta["period_hours"]
        for code, meta in matrix_rows(version).items()
        if meta["part"] == part and answers.get(code) == level
    ]
    return min(candidates) if candidates else None


def _recovery_objective(answers: dict[int, str | None], part: int, version: str) -> float | None:
    medium = _shortest_period_at(answers, part, "Средний", version)
    high = _shortest_period_at(answers, part, "Высокий", version)
    extreme = _shortest_period_at(answers, part, "Крайне высокий", version)
    candidates = [
        value
        for value in (medium, high / 2 if high else None, extreme / 3 if extreme else None)
        if value is not None
    ]
    return round(min(candidates), 4) if candidates else None


def compute(answers: dict[int, str | None], version: str = "v1") -> dict:
    """Scoring output for one survey. `answers` maps matrix question codes to a level."""
    series = _series(answers, version)
    criticality_by_type: dict[str, dict] = {}
    for (part, damage_type), score in series.items():
        bucket = criticality_by_type.setdefault(damage_type, {})
        bucket["availability" if part == AVAILABILITY_PART else "integrity"] = {
            "criticality": score.criticality,
            "answered": score.answered,
            "total": score.total,
            "rows": score.detail,
        }

    all_values = [s.criticality for s in series.values()]
    answered_any = any(s.answered for s in series.values())
    mtpd = _shortest_period_at(answers, AVAILABILITY_PART, "Крайне высокий", version)

    return {
        "overall_criticality": round(max(all_values), 4) if answered_any else None,
        "criticality_by_type": criticality_by_type,
        # No «Крайне высокий» anywhere means the system survives beyond the longest period asked.
        "mtpd_hours": mtpd,
        "mtpd_beyond_scale": mtpd is None and answered_any,
        "rto_hours": _recovery_objective(answers, AVAILABILITY_PART, version),
        "rpo_hours": _recovery_objective(answers, INTEGRITY_PART, version),
    }
