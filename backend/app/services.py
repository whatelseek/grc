"""Survey persistence helpers shared by the routers."""

import uuid

from sqlalchemy.orm import Session

from app.models import Answer, Survey, SurveyResult
from app.scoring import compute
from app.template import matrix_rows
from app.validation import check


def answers_by_code(survey: Survey) -> dict[int, Answer]:
    return {a.question_code: a for a in survey.answers}


def evaluate(survey: Survey) -> dict:
    """Score + validate a survey without touching the database."""
    by_code = answers_by_code(survey)
    grid = matrix_rows(survey.template_version)
    levels = {code: answer.level for code, answer in by_code.items() if code in grid}
    payload = compute(levels, survey.template_version)
    payload.update(check(by_code, survey.template_version))
    return payload


def refresh_result(db: Session, survey: Survey) -> dict:
    """Recompute and persist the result snapshot used by the dashboard."""
    payload = evaluate(survey)
    result = db.get(SurveyResult, survey.id)
    if result is None:
        result = SurveyResult(survey_id=survey.id)
        db.add(result)
    result.overall_criticality = payload["overall_criticality"]
    result.criticality_by_type = payload["criticality_by_type"]
    result.mtpd_hours = payload["mtpd_hours"]
    result.rto_hours = payload["rto_hours"]
    result.rpo_hours = payload["rpo_hours"]
    result.issues = payload["issues"]
    result.progress = payload["progress"]
    db.flush()
    return payload


def upsert_answers(db: Session, survey: Survey, incoming: list) -> None:
    existing = answers_by_code(survey)
    for item in incoming:
        answer = existing.get(item.question_code)
        if answer is None:
            answer = Answer(survey_id=survey.id, question_code=item.question_code)
            db.add(answer)
            survey.answers.append(answer)
            existing[item.question_code] = answer
        answer.text = item.text
        answer.level = item.level
        answer.selections = item.selections
    db.flush()


def survey_payload(survey: Survey, payload: dict | None = None) -> dict:
    data = payload or evaluate(survey)
    return {
        "id": survey.id,
        "system_id": survey.system_id,
        "system_name": survey.system.name if survey.system else None,
        "client_id": survey.system.client_id if survey.system else None,
        "client_name": survey.system.client.name if survey.system else None,
        "status": survey.status,
        "template_version": survey.template_version,
        "assignee_id": survey.assignee_id,
        "updated_at": survey.updated_at,
        "submitted_at": survey.submitted_at,
        "answers": [
            {
                "question_code": a.question_code,
                "text": a.text,
                "level": a.level,
                "selections": a.selections,
            }
            for a in sorted(survey.answers, key=lambda a: a.question_code)
        ],
        "result": data,
    }


def new_survey(db: Session, system_id: uuid.UUID, created_by: uuid.UUID, assignee_id) -> Survey:
    survey = Survey(system_id=system_id, created_by_id=created_by, assignee_id=assignee_id)
    db.add(survey)
    db.flush()
    refresh_result(db, survey)
    return survey
