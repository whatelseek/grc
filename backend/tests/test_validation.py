from app.models import Answer
from app.template import matrix_rows, required_codes
from app.validation import check

GRID = matrix_rows()


def level(code: int, value: str) -> Answer:
    return Answer(question_code=code, level=value)


def codes_for(part: int, damage_type: str) -> list[int]:
    return [
        code
        for code, meta in sorted(GRID.items())
        if meta["part"] == part and meta["damage_type"] == damage_type
    ]


def test_empty_survey_reports_every_required_question():
    report = check({})
    assert report["progress"]["required_filled"] == 0
    assert report["progress"]["required_total"] == len(required_codes()) == 72
    assert len(report["issues"]) == 72
    assert all(issue["severity"] == "missing" for issue in report["issues"])
    assert not report["progress"]["complete"]


def test_softer_level_on_a_longer_period_is_flagged():
    financial = codes_for(3, "financial")
    answers = {
        financial[0]: level(financial[0], "Высокий"),
        financial[1]: level(financial[1], "Средний"),
    }
    report = check(answers)
    warnings = [i for i in report["issues"] if i["severity"] == "warning"]
    assert [w["code"] for w in warnings] == [financial[1]]
    assert "мягче" in warnings[0]["message"]
    assert report["progress"]["warnings"] == 1


def test_non_decreasing_levels_produce_no_warning():
    financial = codes_for(3, "financial")
    rising = ["Низкий", "Низкий", "Средний", "Средний", "Высокий", "Высокий", "Крайне высокий"]
    answers = {c: level(c, v) for c, v in zip(financial, rising)}
    assert [i for i in check(answers)["issues"] if i["severity"] == "warning"] == []


def test_gaps_do_not_break_the_monotonicity_check():
    financial = codes_for(3, "financial")
    answers = {
        financial[0]: level(financial[0], "Средний"),
        financial[4]: level(financial[4], "Низкий"),
    }
    warnings = [i for i in check(answers)["issues"] if i["severity"] == "warning"]
    assert [w["code"] for w in warnings] == [financial[4]]


def test_more_than_three_functional_areas_is_flagged():
    answers = {3: Answer(question_code=3, selections=["a", "b", "c", "d"])}
    warnings = [i for i in check(answers)["issues"] if i["severity"] == "warning"]
    assert [w["code"] for w in warnings] == [3]


def test_optional_questions_are_not_required():
    optional = {5, 6, 7, 13, 14, 15, 79, 80}
    assert optional.isdisjoint(required_codes())


def test_progress_counts_text_and_level_answers():
    answers = {1: Answer(question_code=1, text="Иван, ИТ"), 2: Answer(question_code=2, text="  ")}
    report = check(answers)
    assert report["progress"]["required_filled"] == 1
    missing = {i["code"] for i in report["issues"] if i["severity"] == "missing"}
    assert 1 not in missing and 2 in missing
