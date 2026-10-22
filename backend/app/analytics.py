"""Portfolio-level aggregates behind the analytics page."""

from collections import Counter

from app.models import Survey, SurveyResult
from app.scales import RPO_SCALE_HOURS, RTO_SCALE_HOURS, to_hours

# Part 5 is the owner's own opinion, part 6 the current capability (see the workbook).
STATED_MTPD, STATED_RTO, STATED_RPO = 76, 77, 78
CURRENT_RTO, CURRENT_RPO = 79, 80

BANDS = [
    ("Низкий", 0.0, 0.25),
    ("Средний", 0.25, 0.5),
    ("Высокий", 0.5, 0.75),
    ("Крайне высокий", 0.75, 1.01),
]


def band_for(criticality: float | None) -> str | None:
    if criticality is None:
        return None
    for name, low, high in BANDS:
        if low < criticality <= high or (name == "Низкий" and criticality <= high):
            return name
    return BANDS[-1][0]


def _answer_text(survey: Survey, code: int) -> str | None:
    for answer in survey.answers:
        if answer.question_code == code:
            return (answer.text or "").strip() or None
    return None


def build(rows: list[tuple[Survey, SurveyResult | None]]) -> dict:
    """`rows` are the surveys the caller is allowed to see, with their stored results."""
    profile = Counter()
    statuses = Counter()
    recovery: list[dict] = []
    damage_totals: dict[str, dict[str, list[float]]] = {}
    scored = 0
    complete = 0

    for survey, result in rows:
        statuses[survey.status.value] += 1
        progress = (result.progress if result else {}) or {}
        if progress.get("required_total") and progress["required_filled"] >= progress["required_total"]:
            complete += 1

        criticality = result.overall_criticality if result else None
        band = band_for(criticality)
        if band:
            profile[band] += 1
            scored += 1

        for damage_type, series in ((result.criticality_by_type if result else {}) or {}).items():
            bucket = damage_totals.setdefault(damage_type, {"availability": [], "integrity": []})
            for key in ("availability", "integrity"):
                value = (series.get(key) or {}).get("criticality")
                answered = (series.get(key) or {}).get("answered")
                if value is not None and answered:
                    bucket[key].append(value)

        current_rto, rto_beyond = to_hours(_answer_text(survey, CURRENT_RTO), RTO_SCALE_HOURS)
        current_rpo, rpo_beyond = to_hours(_answer_text(survey, CURRENT_RPO), RPO_SCALE_HOURS)
        stated_rto, _ = to_hours(_answer_text(survey, STATED_RTO), RTO_SCALE_HOURS)
        stated_rpo, _ = to_hours(_answer_text(survey, STATED_RPO), RPO_SCALE_HOURS)
        required_rto = result.rto_hours if result else None
        required_rpo = result.rpo_hours if result else None

        if required_rto is not None or required_rpo is not None:
            recovery.append(
                {
                    "survey_id": str(survey.id),
                    "system_name": survey.system.name,
                    "client_name": survey.system.client.name,
                    "criticality": criticality,
                    "band": band,
                    "required_rto": required_rto,
                    "current_rto": current_rto,
                    "current_rto_beyond_scale": rto_beyond,
                    "stated_rto": stated_rto,
                    "required_rpo": required_rpo,
                    "current_rpo": current_rpo,
                    "current_rpo_beyond_scale": rpo_beyond,
                    "stated_rpo": stated_rpo,
                    # A gap means the system recovers slower than the damage profile allows.
                    "rto_gap": _gap(required_rto, current_rto, rto_beyond),
                    "rpo_gap": _gap(required_rpo, current_rpo, rpo_beyond),
                }
            )

    damage_profile = [
        {
            "damage_type": damage_type,
            "availability": _mean(values["availability"]),
            "integrity": _mean(values["integrity"]),
            "systems": max(len(values["availability"]), len(values["integrity"])),
        }
        for damage_type, values in sorted(damage_totals.items())
    ]

    return {
        "kpis": {
            "surveys_total": len(rows),
            "surveys_scored": scored,
            "surveys_complete": complete,
            "high_criticality": profile["Высокий"] + profile["Крайне высокий"],
            "rto_gaps": sum(1 for row in recovery if row["rto_gap"] is not None and row["rto_gap"] > 0),
            "rpo_gaps": sum(1 for row in recovery if row["rpo_gap"] is not None and row["rpo_gap"] > 0),
        },
        "criticality_profile": [
            {"band": name, "count": profile[name]} for name, _, _ in BANDS
        ],
        "collection": [
            {"status": status, "count": statuses.get(status, 0)}
            for status in ("draft", "submitted", "reviewed")
        ],
        "recovery": sorted(
            recovery,
            key=lambda row: (row["rto_gap"] is None, -(row["rto_gap"] or 0), row["system_name"]),
        ),
        "damage_profile": damage_profile,
    }


def _gap(required: float | None, current: float | None, beyond_scale: bool) -> float | None:
    """Hours by which the current capability misses the objective; None when unknown."""
    if required is None:
        return None
    if beyond_scale:
        # Worse than the longest option offered, so the gap is at least this big.
        return max(0.0, 168 - required) or 168
    if current is None:
        return None
    return round(current - required, 4)


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None
