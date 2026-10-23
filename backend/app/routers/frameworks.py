"""Administration of the requirements catalogue.

Published versions are frozen. To change requirements an admin creates a draft from a
published version, edits it, and publishes it; assessments keep pointing at the version
they were carried out against until they are migrated explicitly.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import catalogue as store
from app.db import get_db
from app.deps import current_user, require_admin
from app.models import (
    Assessment,
    Framework,
    FrameworkControl,
    FrameworkSafeguard,
    FrameworkStatus,
    User,
)
from app.schemas import (
    ControlIn,
    ControlUpdate,
    FrameworkDraftIn,
    FrameworkOut,
    FrameworkUpdate,
    SafeguardIn,
    SafeguardUpdate,
)

router = APIRouter(prefix="/api/frameworks", tags=["frameworks"])


def _usage(db: Session) -> dict[uuid.UUID, int]:
    rows = db.execute(
        select(Assessment.framework_id, func.count(Assessment.id)).group_by(Assessment.framework_id)
    ).all()
    return {framework_id: count for framework_id, count in rows if framework_id}


def _out(framework: Framework, used: int = 0) -> FrameworkOut:
    return FrameworkOut(
        id=framework.id,
        key=framework.key,
        version=framework.version,
        title=framework.title,
        source=framework.source,
        status=framework.status,
        notes=framework.notes,
        derived_from_id=framework.derived_from_id,
        created_at=framework.created_at,
        published_at=framework.published_at,
        control_count=len(framework.controls),
        safeguard_count=sum(len(control.safeguards) for control in framework.controls),
        custom_count=sum(
            1 for control in framework.controls for s in control.safeguards if s.is_custom
        ),
        assessments_using=used,
    )


def _editable(db: Session, framework_id: uuid.UUID) -> Framework:
    framework = db.get(Framework, framework_id)
    if framework is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Версия каталога не найдена")
    if framework.status is not FrameworkStatus.draft:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Опубликованная версия неизменна. Создайте черновик, чтобы править требования: "
            "так оценки, проведённые по ней, останутся прежними.",
        )
    return framework


@router.get("", response_model=list[FrameworkOut])
def list_frameworks(_: User = Depends(current_user), db: Session = Depends(get_db)) -> list[FrameworkOut]:
    used = _usage(db)
    frameworks = db.scalars(select(Framework).order_by(Framework.created_at.desc())).all()
    return [_out(framework, used.get(framework.id, 0)) for framework in frameworks]


@router.get("/{framework_id}")
def get_framework(
    framework_id: uuid.UUID, _: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    framework = db.get(Framework, framework_id)
    if framework is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Версия каталога не найдена")
    return store.as_dict(framework)


@router.post("/{framework_id}/draft", response_model=FrameworkOut, status_code=status.HTTP_201_CREATED)
def create_draft(
    framework_id: uuid.UUID,
    payload: FrameworkDraftIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FrameworkOut:
    """Copy a version into a new draft — the only way to change published requirements."""
    source = db.get(Framework, framework_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Версия каталога не найдена")
    exists = db.scalar(
        select(Framework).where(Framework.key == source.key, Framework.version == payload.version)
    )
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Версия {payload.version} уже существует")
    draft = store.clone(db, source, payload.version, admin.id)
    draft.notes = payload.notes
    db.commit()
    return _out(draft)


@router.patch("/{framework_id}", response_model=FrameworkOut)
def update_framework(
    framework_id: uuid.UUID,
    payload: FrameworkUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FrameworkOut:
    framework = _editable(db, framework_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(framework, field, value)
    db.commit()
    return _out(framework)


@router.post("/{framework_id}/publish", response_model=FrameworkOut)
def publish(
    framework_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> FrameworkOut:
    framework = _editable(db, framework_id)
    if not framework.controls:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "В каталоге нет ни одного требования")
    framework.status = FrameworkStatus.published
    framework.published_at = datetime.now(timezone.utc)
    db.commit()
    return _out(framework)


@router.post("/{framework_id}/archive", response_model=FrameworkOut)
def archive(
    framework_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> FrameworkOut:
    """Archived versions stay readable for past assessments but are not offered for new ones."""
    framework = db.get(Framework, framework_id)
    if framework is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Версия каталога не найдена")
    framework.status = FrameworkStatus.archived
    db.commit()
    return _out(framework, _usage(db).get(framework.id, 0))


@router.delete("/{framework_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_framework(
    framework_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> None:
    framework = _editable(db, framework_id)
    if _usage(db).get(framework.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "По этой версии уже проводились оценки")
    db.delete(framework)
    db.commit()


@router.post("/{framework_id}/controls", status_code=status.HTTP_201_CREATED)
def create_control(
    framework_id: uuid.UUID,
    payload: ControlIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    framework = _editable(db, framework_id)
    if any(control.number == payload.number for control in framework.controls):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Контроль {payload.number} уже есть")
    control = FrameworkControl(
        framework_id=framework.id,
        number=payload.number,
        title=payload.title,
        description=payload.description,
        position=payload.position if payload.position is not None else len(framework.controls),
    )
    db.add(control)
    db.commit()
    # The controls collection was loaded before the insert.
    db.refresh(framework)
    return store.as_dict(framework)


@router.patch("/controls/{control_id}")
def update_control(
    control_id: uuid.UUID,
    payload: ControlUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    control = db.get(FrameworkControl, control_id)
    if control is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Контроль не найден")
    framework = _editable(db, control.framework_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(control, field, value)
    db.commit()
    db.refresh(framework)
    return store.as_dict(framework)


@router.delete("/controls/{control_id}")
def delete_control(
    control_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    control = db.get(FrameworkControl, control_id)
    if control is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Контроль не найден")
    framework = _editable(db, control.framework_id)
    db.delete(control)
    db.commit()
    db.refresh(framework)
    return store.as_dict(framework)


@router.post("/{framework_id}/safeguards", status_code=status.HTTP_201_CREATED)
def create_safeguard(
    framework_id: uuid.UUID,
    payload: SafeguardIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    framework = _editable(db, framework_id)
    control = db.get(FrameworkControl, payload.control_id)
    if control is None or control.framework_id != framework.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Контроль не найден в этой версии")
    if db.scalar(
        select(FrameworkSafeguard).where(
            FrameworkSafeguard.framework_id == framework.id,
            FrameworkSafeguard.code == payload.code,
        )
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Требование {payload.code} уже есть")

    db.add(
        FrameworkSafeguard(
            framework_id=framework.id,
            control_id=control.id,
            code=payload.code,
            title=payload.title,
            description=payload.description,
            asset_class=payload.asset_class,
            security_function=payload.security_function,
            ig=payload.ig,
            position=payload.position if payload.position is not None else len(control.safeguards),
            is_custom=True,
        )
    )
    db.commit()
    db.refresh(framework)
    return store.as_dict(framework)


@router.patch("/safeguards/{safeguard_id}")
def update_safeguard(
    safeguard_id: uuid.UUID,
    payload: SafeguardUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    safeguard = db.get(FrameworkSafeguard, safeguard_id)
    if safeguard is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Требование не найдено")
    framework = _editable(db, safeguard.framework_id)
    fields = payload.model_dump(exclude_unset=True)
    if "code" in fields and fields["code"] and fields["code"] != safeguard.code:
        if db.scalar(
            select(FrameworkSafeguard).where(
                FrameworkSafeguard.framework_id == framework.id,
                FrameworkSafeguard.code == fields["code"],
            )
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, f"Требование {fields['code']} уже есть")
    for field, value in fields.items():
        if value is not None:
            setattr(safeguard, field, value)
    db.commit()
    db.refresh(framework)
    return store.as_dict(framework)


@router.delete("/safeguards/{safeguard_id}")
def delete_safeguard(
    safeguard_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    safeguard = db.get(FrameworkSafeguard, safeguard_id)
    if safeguard is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Требование не найдено")
    framework = _editable(db, safeguard.framework_id)
    db.delete(safeguard)
    db.commit()
    db.refresh(framework)
    return store.as_dict(framework)
