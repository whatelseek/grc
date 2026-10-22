import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import (
    current_user,
    get_client_for_user,
    get_survey_for_user,
    require_editor,
    scoped_surveys,
)
from app.models import Survey, SurveyStatus, System, User
from app.schemas import AnswersPatch, SurveyCreate, SurveyDetail, SurveyOut
from app.services import new_survey, refresh_result, survey_payload, upsert_answers
from app.template import load_template, matrix_rows, plain_questions

router = APIRouter(prefix="/api/surveys", tags=["surveys"])


@router.get("", response_model=list[SurveyOut])
def list_surveys(
    client_id: uuid.UUID | None = None,
    system_id: uuid.UUID | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[SurveyOut]:
    stmt = scoped_surveys(db, user)
    if client_id is not None:
        get_client_for_user(db, user, client_id)
        stmt = stmt.where(System.client_id == client_id)
    if system_id is not None:
        stmt = stmt.where(Survey.system_id == system_id)
    surveys = list(db.scalars(stmt.order_by(Survey.updated_at.desc())))
    return [
        SurveyOut(
            id=s.id,
            system_id=s.system_id,
            system_name=s.system.name,
            client_id=s.system.client_id,
            client_name=s.system.client.name,
            status=s.status,
            template_version=s.template_version,
            assignee_id=s.assignee_id,
            updated_at=s.updated_at,
            submitted_at=s.submitted_at,
        )
        for s in surveys
    ]


@router.post("", response_model=SurveyDetail, status_code=status.HTTP_201_CREATED)
def create_survey(
    payload: SurveyCreate, user: User = Depends(require_editor), db: Session = Depends(get_db)
) -> SurveyDetail:
    system = db.get(System, payload.system_id)
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "System not found")
    get_client_for_user(db, user, system.client_id)
    survey = new_survey(db, system.id, user.id, payload.assignee_id)
    db.commit()
    return SurveyDetail(**survey_payload(survey))


@router.get("/{survey_id}", response_model=SurveyDetail)
def get_survey(
    survey_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> SurveyDetail:
    survey = get_survey_for_user(db, user, survey_id)
    return SurveyDetail(**survey_payload(survey))


@router.patch("/{survey_id}/answers", response_model=SurveyDetail)
def save_answers(
    survey_id: uuid.UUID,
    payload: AnswersPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> SurveyDetail:
    """Autosave endpoint: accepts a partial set of answers and returns fresh scores/issues."""
    survey = get_survey_for_user(db, user, survey_id)
    if survey.status is SurveyStatus.reviewed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Survey is closed for editing")

    known = set(matrix_rows(survey.template_version)) | set(plain_questions(survey.template_version))
    unknown = [a.question_code for a in payload.answers if a.question_code not in known]
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown question codes: {unknown}")
    levels = set(load_template(survey.template_version)["levels"])
    bad_levels = [a.level for a in payload.answers if a.level and a.level not in levels]
    if bad_levels:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown damage levels: {bad_levels}")

    upsert_answers(db, survey, payload.answers)
    result = refresh_result(db, survey)
    db.commit()
    return SurveyDetail(**survey_payload(survey, result))


@router.post("/{survey_id}/submit", response_model=SurveyDetail)
def submit(
    survey_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> SurveyDetail:
    survey = get_survey_for_user(db, user, survey_id)
    result = refresh_result(db, survey)
    progress = result["progress"]
    if progress["required_filled"] < progress["required_total"]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Заполнено {progress['required_filled']} из {progress['required_total']} "
            "обязательных вопросов",
        )
    survey.status = SurveyStatus.submitted
    survey.submitted_at = datetime.now(timezone.utc)
    db.commit()
    return SurveyDetail(**survey_payload(survey, result))


@router.post("/{survey_id}/reopen", response_model=SurveyDetail)
def reopen(
    survey_id: uuid.UUID, user: User = Depends(require_editor), db: Session = Depends(get_db)
) -> SurveyDetail:
    survey = get_survey_for_user(db, user, survey_id)
    survey.status = SurveyStatus.draft
    survey.submitted_at = None
    db.commit()
    return SurveyDetail(**survey_payload(survey))


@router.post("/{survey_id}/review", response_model=SurveyDetail)
def mark_reviewed(
    survey_id: uuid.UUID, user: User = Depends(require_editor), db: Session = Depends(get_db)
) -> SurveyDetail:
    survey = get_survey_for_user(db, user, survey_id)
    if survey.status is SurveyStatus.draft:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Survey has not been submitted yet")
    survey.status = SurveyStatus.reviewed
    db.commit()
    return SurveyDetail(**survey_payload(survey))


@router.delete("/{survey_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_survey(
    survey_id: uuid.UUID, user: User = Depends(require_editor), db: Session = Depends(get_db)
) -> None:
    survey = get_survey_for_user(db, user, survey_id)
    db.delete(survey)
    db.commit()
