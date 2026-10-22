import csv
import io
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, get_client_for_user, scoped_surveys
from app.models import Survey, SurveyResult, System, User
from app.schemas import DashboardRow

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Part 5 holds the owner's own MTPD/RTO/RPO opinion, part 6 the current DR capability.
STATED_MTPD, STATED_RTO, STATED_RPO = 76, 77, 78
CURRENT_RTO, CURRENT_RPO = 79, 80


def _rows(db: Session, user: User, client_id: uuid.UUID | None) -> list[DashboardRow]:
    stmt = scoped_surveys(db, user)
    if client_id is not None:
        get_client_for_user(db, user, client_id)
        stmt = stmt.where(System.client_id == client_id)

    rows: list[DashboardRow] = []
    for survey in db.scalars(stmt.order_by(Survey.updated_at.desc())):
        result = db.get(SurveyResult, survey.id)
        answers = {a.question_code: a for a in survey.answers}
        progress = (result.progress if result else {}) or {}

        def text(code: int) -> str | None:
            answer = answers.get(code)
            return (answer.text or None) if answer else None

        rows.append(
            DashboardRow(
                survey_id=survey.id,
                client_id=survey.system.client_id,
                client_name=survey.system.client.name,
                system_id=survey.system_id,
                system_name=survey.system.name,
                business_owner=survey.system.business_owner,
                it_owner=survey.system.it_owner,
                status=survey.status,
                overall_criticality=result.overall_criticality if result else None,
                mtpd_hours=result.mtpd_hours if result else None,
                rto_hours=result.rto_hours if result else None,
                rpo_hours=result.rpo_hours if result else None,
                stated_mtpd=text(STATED_MTPD),
                stated_rto=text(STATED_RTO),
                stated_rpo=text(STATED_RPO),
                current_rto=text(CURRENT_RTO),
                current_rpo=text(CURRENT_RPO),
                required_filled=progress.get("required_filled", 0),
                required_total=progress.get("required_total", 0),
                warnings=progress.get("warnings", 0),
                updated_at=survey.updated_at,
            )
        )
    return rows


@router.get("", response_model=list[DashboardRow])
def dashboard(
    client_id: uuid.UUID | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[DashboardRow]:
    return _rows(db, user, client_id)


@router.get("/export.csv")
def export_csv(
    client_id: uuid.UUID | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows = _rows(db, user, client_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "Клиент",
            "Система",
            "Владелец процесса",
            "ИТ-владелец",
            "Статус",
            "Общая критичность",
            "MTPD, ч (расчёт)",
            "RTO, ч (расчёт)",
            "RPO, ч (расчёт)",
            "MTPD (мнение)",
            "RTO (мнение)",
            "RPO (мнение)",
            "RTO сейчас",
            "RPO сейчас",
            "Заполнено",
            "Замечаний",
            "Обновлено",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.client_name,
                row.system_name,
                row.business_owner,
                row.it_owner,
                row.status.value,
                "" if row.overall_criticality is None else f"{row.overall_criticality:.2f}",
                "" if row.mtpd_hours is None else row.mtpd_hours,
                "" if row.rto_hours is None else row.rto_hours,
                "" if row.rpo_hours is None else row.rpo_hours,
                row.stated_mtpd or "",
                row.stated_rto or "",
                row.stated_rpo or "",
                row.current_rto or "",
                row.current_rpo or "",
                f"{row.required_filled}/{row.required_total}",
                row.warnings,
                row.updated_at.strftime("%Y-%m-%d %H:%M"),
            ]
        )
    # BOM so Excel opens the semicolon-separated file with the right encoding.
    data = "﻿" + buffer.getvalue()
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="bia-dashboard.csv"'},
    )
