"""Parity checks against the workbook's «Расчет» sheet."""

from app.scoring import compute
from app.template import matrix_rows

GRID = matrix_rows()
AVAILABILITY = {code: m for code, m in GRID.items() if m["part"] == 3}
INTEGRITY = {code: m for code, m in GRID.items() if m["part"] == 4}


def codes_for(part: int, damage_type: str) -> list[int]:
    return [
        code
        for code, meta in sorted(GRID.items())
        if meta["part"] == part and meta["damage_type"] == damage_type
    ]


def test_weights_of_each_series_sum_to_one():
    for part in (3, 4):
        for damage_type in ("financial", "regulatory", "operational", "reputational"):
            weights = [GRID[c]["weight"] for c in codes_for(part, damage_type)]
            assert round(sum(weights), 6) == 1.0


def test_grid_covers_questions_20_to_75():
    assert sorted(GRID) == list(range(20, 76))


def test_all_extreme_gives_full_criticality_and_tightest_objectives():
    result = compute({code: "Крайне высокий" for code in GRID})
    assert result["overall_criticality"] == 1.0
    # Shortest downtime period asked about is 30 minutes.
    assert result["mtpd_hours"] == 0.5
    # RTO = 1/3 of the shortest period reaching «Крайне высокий».
    assert result["rto_hours"] == round(0.5 / 3, 4)
    # Integrity scale starts at 2 minutes.
    assert result["rpo_hours"] == round((2 / 60) / 3, 4)


def test_all_low_gives_quarter_criticality_and_no_mtpd():
    result = compute({code: "Низкий" for code in GRID})
    assert result["overall_criticality"] == 0.25
    assert result["mtpd_hours"] is None
    assert result["mtpd_beyond_scale"] is True
    # «Низкий» never triggers an RTO threshold.
    assert result["rto_hours"] is None


def test_empty_survey_scores_nothing():
    result = compute({})
    assert result["overall_criticality"] is None
    assert result["mtpd_beyond_scale"] is False
    assert result["rto_hours"] is None


def test_overall_criticality_is_max_across_series():
    answers = {code: "Низкий" for code in GRID}
    for code in codes_for(3, "financial"):
        answers[code] = "Крайне высокий"
    result = compute(answers)
    assert result["overall_criticality"] == 1.0
    financial = result["criticality_by_type"]["financial"]
    assert financial["availability"]["criticality"] == 1.0
    assert financial["integrity"]["criticality"] == 0.25


def test_rto_takes_the_minimum_of_the_three_rules():
    answers = {}
    financial = codes_for(3, "financial")
    # «Средний» at 8 hours, «Высокий» at 24 hours -> min(8, 24/2) = 8.
    answers[financial[2]] = "Средний"
    answers[financial[3]] = "Высокий"
    assert compute(answers)["rto_hours"] == 8
    # Add «Крайне высокий» at 24 hours -> 24/3 = 8 stays the minimum.
    answers[financial[3]] = "Крайне высокий"
    assert compute(answers)["rto_hours"] == 8
    # Move «Крайне высокий» to 3 days: min(8, 72/3) = 8.
    del answers[financial[3]]
    answers[financial[4]] = "Крайне высокий"
    assert compute(answers)["rto_hours"] == 8
    assert compute(answers)["mtpd_hours"] == 72


def test_weighted_sum_matches_hand_calculation():
    financial = codes_for(3, "financial")
    answers = {financial[0]: "Средний", financial[1]: "Высокий"}
    expected = 0.5 * 0.30 + 0.75 * 0.25
    series = compute(answers)["criticality_by_type"]["financial"]["availability"]
    assert series["criticality"] == round(expected, 4)
    assert series["answered"] == 2
    assert series["total"] == 7
