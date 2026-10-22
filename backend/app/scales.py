"""Turn the questionnaire's dropdown answers into hours, so stated and current
recovery capability can be compared with the calculated objectives.

The labels come from the «Списки» sheet (see questionnaire_v1.json option_lists);
a label that means "longer than the scale" maps to None and is reported separately.
"""

RTO_SCALE_HOURS: dict[str, float | None] = {
    "15 минут": 0.25,
    "30 минут": 0.5,
    "1 час": 1,
    "4 часа": 4,
    "8 часов": 8,
    "24 часа": 24,
    "3 суток": 72,
    "7 суток": 168,
    "более 7 суток": None,
}

RPO_SCALE_HOURS: dict[str, float | None] = {
    "0 (потеря недопустима)": 0,
    "2 минуты": 2 / 60,
    "15 минут": 0.25,
    "2 часа": 2,
    "8 часов": 8,
    "24 часа": 24,
    "3 суток": 72,
    "7 суток": 168,
    "2 недели": 336,
    "более 2 недель": None,
}


def to_hours(label: str | None, scale: dict[str, float | None]) -> tuple[float | None, bool]:
    """Return (hours, beyond_scale). Both are None/False for an unanswered question."""
    if not label:
        return None, False
    text = label.strip()
    if text not in scale:
        return None, False
    value = scale[text]
    return (None, True) if value is None else (value, False)
