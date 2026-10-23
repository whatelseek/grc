import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import catalogue as catalogue_store
from app import comparison
from app.cis_scoring import compute
from app.db import get_db
from app.deps import current_user, get_client_for_user, require_editor, visible_client_ids
from app.frameworks import DEFAULT_FRAMEWORK
from app.models import (
    Assessment,
    AssessmentItem,
    AssessmentItemHistory,
    AssessmentStatus,
    Client,
    FrameworkStatus,
    ImplementationStatus,
    User,
)
from app.schemas import (
    AssessmentCreate,
    AssessmentDetail,
    AssessmentOut,
    AssessmentUpdate,
    ItemsPatch,
    MigrateIn,
)

router = APIRouter(prefix="/api/assessments", tags=["assessments"])

STATUS_LABELS = {
    "not_implemented": "Не внедрено",
    "partial": "Частично",
    "implemented": "Внедрено",
    "not_applicable": "Не применимо",
}
PRIORITY_LABELS = {"high": "высокий", "medium": "средний", "low": "низкий"}


def _scoped(db: Session, user: User):
    stmt = select(Assessment).join(Client)
    allowed = visible_client_ids(db, user)
    if allowed is not None:
        stmt = stmt.where(Client.id.in_(allowed or [uuid.uuid4()]))
    return stmt


def _get_for_user(db: Session, user: User, assessment_id: uuid.UUID) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Оценка не найдена")
    get_client_for_user(db, user, assessment.client_id)
    return assessment


def _catalogue(assessment: Assessment) -> dict[str, dict]:
    if assessment.catalogue is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "У оценки не указана версия каталога требований",
        )
    return catalogue_store.safeguards_of(assessment.catalogue)


def _result(assessment: Assessment) -> dict:
    return compute(assessment.items, assessment.target_ig, _catalogue(assessment))


def _summary(assessment: Assessment, result: dict | None = None) -> dict:
    data = result or _result(assessment)
    return {
        "id": assessment.id,
        "client_id": assessment.client_id,
        "client_name": assessment.client.name if assessment.client else None,
        "framework": assessment.framework,
        "framework_version": assessment.framework_version,
        "framework_id": assessment.framework_id,
        "name": assessment.name,
        "target_ig": assessment.target_ig,
        "status": assessment.status,
        "assessor_id": assessment.assessor_id,
        "created_at": assessment.created_at,
        "updated_at": assessment.updated_at,
        "completed_at": assessment.completed_at,
        "implementation": data["overall"]["implementation"],
        "gaps_open": len(data["gaps"]),
    }


@router.get("/framework")
def framework(
    framework_id: uuid.UUID | None = None,
    key: str = DEFAULT_FRAMEWORK,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """The catalogue the UI renders: a specific version, or the current published one."""
    record = (
        catalogue_store.get(db, framework_id)
        if framework_id is not None
        else catalogue_store.published(db, key)
    )
    if record is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Каталог требований не загружен. Выполните `python -m app.cli import-framework`.",
        )
    return catalogue_store.as_dict(record)


@router.get("", response_model=list[AssessmentOut])
def list_assessments(
    client_id: uuid.UUID | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[AssessmentOut]:
    stmt = _scoped(db, user)
    if client_id is not None:
        get_client_for_user(db, user, client_id)
        stmt = stmt.where(Assessment.client_id == client_id)
    return [
        AssessmentOut(**_summary(assessment))
        for assessment in db.scalars(stmt.order_by(Assessment.updated_at.desc()))
    ]


@router.post("", response_model=AssessmentDetail, status_code=status.HTTP_201_CREATED)
def create_assessment(
    payload: AssessmentCreate, user: User = Depends(require_editor), db: Session = Depends(get_db)
) -> AssessmentDetail:
    client = get_client_for_user(db, user, payload.client_id)
    record = (
        catalogue_store.get(db, payload.framework_id)
        if payload.framework_id is not None
        else catalogue_store.published(db, DEFAULT_FRAMEWORK)
    )
    if record is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Нет опубликованного каталога требований, по которому можно проводить оценку",
        )
    assessment = Assessment(
        client_id=client.id,
        name=payload.name or f"{record.title} — {client.name}",
        target_ig=payload.target_ig,
        assessor_id=payload.assessor_id or user.id,
        framework=record.key,
        framework_version=record.version,
        framework_id=record.id,
    )
    db.add(assessment)
    db.commit()
    return AssessmentDetail(**_detail(assessment))


def _detail(assessment: Assessment, result: dict | None = None) -> dict:
    data = result or _result(assessment)
    return {
        **_summary(assessment, data),
        "items": sorted(assessment.items, key=lambda item: _sort_key(item.safeguard_id)),
        "result": data,
    }


def _as_text(value) -> str | None:
    if value is None or value == "":
        return None
    return getattr(value, "value", None) or str(value)


def _sort_key(safeguard_id: str) -> tuple[int, int]:
    control, _, position = safeguard_id.partition(".")
    return int(control), int(position or 0)


@router.get("/compare")
def compare(
    base: uuid.UUID,
    target: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Progress between two audits of one client, requirement by requirement."""
    first = _get_for_user(db, user, base)
    second = _get_for_user(db, user, target)
    if first.client_id != second.client_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Сравнивать можно только оценки одного клиента"
        )
    if first.id == second.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Выберите две разные оценки")
    return comparison.build(first, second, _catalogue(first), _catalogue(second))


@router.get("/{assessment_id}", response_model=AssessmentDetail)
def get_assessment(
    assessment_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> AssessmentDetail:
    return AssessmentDetail(**_detail(_get_for_user(db, user, assessment_id)))


@router.patch("/{assessment_id}", response_model=AssessmentDetail)
def update_assessment(
    assessment_id: uuid.UUID,
    payload: AssessmentUpdate,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
) -> AssessmentDetail:
    assessment = _get_for_user(db, user, assessment_id)
    fields = payload.model_dump(exclude_unset=True)
    for field, value in fields.items():
        if value is not None:
            setattr(assessment, field, value)
    if fields.get("status") is AssessmentStatus.completed:
        assessment.completed_at = datetime.now(timezone.utc)
    elif "status" in fields:
        assessment.completed_at = None
    db.commit()
    return AssessmentDetail(**_detail(assessment))


@router.patch("/{assessment_id}/items", response_model=AssessmentDetail)
def save_items(
    assessment_id: uuid.UUID,
    payload: ItemsPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AssessmentDetail:
    """Autosave for the checklist: a partial set of safeguards comes back scored."""
    assessment = _get_for_user(db, user, assessment_id)
    if assessment.status is AssessmentStatus.completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Оценка завершена и закрыта для правок")

    catalogue = _catalogue(assessment)
    unknown = [item.safeguard_id for item in payload.items if item.safeguard_id not in catalogue]
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Неизвестные меры защиты: {unknown}")

    existing = {item.safeguard_id: item for item in assessment.items}
    for incoming in payload.items:
        item = existing.get(incoming.safeguard_id)
        if item is None:
            item = AssessmentItem(assessment_id=assessment.id, safeguard_id=incoming.safeguard_id)
            db.add(item)
            assessment.items.append(item)
            existing[incoming.safeguard_id] = item
        fields = incoming.model_dump(exclude_unset=True, exclude={"safeguard_id"})
        for field, value in fields.items():
            if field in ("owner", "notes") and value is None:
                value = ""
            before = getattr(item, field)
            if before == value:
                continue
            setattr(item, field, value)
            db.add(
                AssessmentItemHistory(
                    assessment_id=assessment.id,
                    safeguard_code=incoming.safeguard_id,
                    field=field,
                    old_value=_as_text(before),
                    new_value=_as_text(value),
                    changed_by_id=user.id,
                )
            )

    if assessment.status is AssessmentStatus.draft:
        assessment.status = AssessmentStatus.in_progress
    db.flush()
    db.commit()
    return AssessmentDetail(**_detail(assessment))


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(
    assessment_id: uuid.UUID, user: User = Depends(require_editor), db: Session = Depends(get_db)
) -> None:
    db.delete(_get_for_user(db, user, assessment_id))
    db.commit()


@router.get("/{assessment_id}/history")
def history(
    assessment_id: uuid.UUID,
    safeguard_id: str | None = None,
    limit: int = 200,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Who changed which verdict, when, and from what — the audit trail of the audit."""
    assessment = _get_for_user(db, user, assessment_id)
    stmt = (
        select(AssessmentItemHistory)
        .where(AssessmentItemHistory.assessment_id == assessment.id)
        .order_by(AssessmentItemHistory.changed_at.desc())
        .limit(min(limit, 1000))
    )
    if safeguard_id is not None:
        stmt = stmt.where(AssessmentItemHistory.safeguard_code == safeguard_id)
    return [
        {
            "id": str(entry.id),
            "safeguard_id": entry.safeguard_code,
            "field": entry.field,
            "old_value": entry.old_value,
            "new_value": entry.new_value,
            "changed_at": entry.changed_at.isoformat(),
            "changed_by": entry.changed_by.full_name or entry.changed_by.email
            if entry.changed_by
            else None,
        }
        for entry in db.scalars(stmt)
    ]


@router.post("/{assessment_id}/migrate", response_model=AssessmentDetail)
def migrate(
    assessment_id: uuid.UUID,
    payload: MigrateIn,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
) -> AssessmentDetail:
    """Move an audit onto another catalogue version, keeping the verdicts that still apply."""
    assessment = _get_for_user(db, user, assessment_id)
    if assessment.status is AssessmentStatus.completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Завершённую оценку переносить нельзя")

    target = catalogue_store.get(db, payload.framework_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Версия каталога не найдена")
    if target.status is FrameworkStatus.draft:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Нельзя проводить оценку по неопубликованному черновику"
        )

    codes = set(catalogue_store.safeguards_of(target))
    dropped = [item.safeguard_id for item in assessment.items if item.safeguard_id not in codes]
    for item in list(assessment.items):
        if item.safeguard_id in dropped:
            # The requirement no longer exists in the target version; its verdict goes,
            # but the history keeps what it was.
            db.add(
                AssessmentItemHistory(
                    assessment_id=assessment.id,
                    safeguard_code=item.safeguard_id,
                    field="migrated_out",
                    old_value=item.status.value,
                    new_value=None,
                    changed_by_id=user.id,
                )
            )
            assessment.items.remove(item)
            db.delete(item)

    db.add(
        AssessmentItemHistory(
            assessment_id=assessment.id,
            safeguard_code="-",
            field="framework_version",
            old_value=assessment.framework_version,
            new_value=target.version,
            changed_by_id=user.id,
        )
    )
    assessment.framework_id = target.id
    assessment.framework = target.key
    assessment.framework_version = target.version
    db.commit()
    return AssessmentDetail(**_detail(assessment))


@router.get("/{assessment_id}/remediation.csv")
def remediation_csv(
    assessment_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> StreamingResponse:
    assessment = _get_for_user(db, user, assessment_id)
    gaps = _result(assessment)["gaps"]

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        ["Мера", "Контроль", "Название", "IG", "Функция", "Статус", "Приоритет", "Ответственный", "Срок", "Комментарий"]
    )
    for gap in gaps:
        writer.writerow(
            [
                gap["safeguard_id"],
                f"{gap['control']}. {gap['control_title']}",
                gap["title"],
                f"IG{gap['ig']}",
                gap["security_function"] or "",
                STATUS_LABELS.get(gap["status"], gap["status"]),
                PRIORITY_LABELS.get(gap["priority"] or "", ""),
                gap["owner"],
                gap["due_date"] or "",
                gap["notes"].replace("\n", " "),
            ]
        )
    data = "﻿" + buffer.getvalue()
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cis-remediation.csv"'},
    )


__all__ = ["router", "ImplementationStatus"]
