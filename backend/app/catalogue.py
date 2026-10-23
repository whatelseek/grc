"""The requirements catalogue as stored in the database.

A framework version is a snapshot of requirements. Published versions are frozen:
`clone` makes a new draft to edit, and assessments keep pointing at the version they
were carried out against, so an edit today cannot move last quarter's result.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.frameworks import load_framework
from app.models import Framework, FrameworkControl, FrameworkSafeguard, FrameworkStatus


def published(db: Session, key: str = "cis") -> Framework | None:
    """The newest published version of a catalogue — what a new assessment uses."""
    return db.scalars(
        select(Framework)
        .where(Framework.key == key, Framework.status == FrameworkStatus.published)
        .order_by(Framework.published_at.desc().nullslast(), Framework.created_at.desc())
    ).first()


def get(db: Session, framework_id: uuid.UUID) -> Framework | None:
    return db.get(Framework, framework_id)


def safeguards_of(framework: Framework) -> dict[str, dict]:
    """code -> requirement, with its control attached, as the scoring expects."""
    out: dict[str, dict] = {}
    for control in framework.controls:
        for safeguard in control.safeguards:
            out[safeguard.code] = {
                "id": safeguard.code,
                "title": safeguard.title,
                "description": safeguard.description,
                "asset_class": safeguard.asset_class,
                "security_function": safeguard.security_function,
                "ig": safeguard.ig,
                "is_custom": safeguard.is_custom,
                "control": control.number,
                "control_title": control.title,
            }
    return out


def as_dict(framework: Framework) -> dict:
    return {
        "id": str(framework.id),
        "key": framework.key,
        "version": framework.version,
        "title": framework.title,
        "source": framework.source,
        "status": framework.status.value,
        "notes": framework.notes,
        "derived_from_id": str(framework.derived_from_id) if framework.derived_from_id else None,
        "created_at": framework.created_at.isoformat() if framework.created_at else None,
        "published_at": framework.published_at.isoformat() if framework.published_at else None,
        "asset_classes": sorted(
            {s.asset_class for c in framework.controls for s in c.safeguards if s.asset_class}
        ),
        "security_functions": sorted(
            {s.security_function for c in framework.controls for s in c.safeguards if s.security_function}
        ),
        "implementation_groups": [
            {"level": 1, "title": "IG1", "description": "Базовая кибергигиена: минимум для любой организации"},
            {"level": 2, "title": "IG2", "description": "Организации, управляющие ИТ для нескольких подразделений"},
            {"level": 3, "title": "IG3", "description": "Организации с выделенной функцией ИБ"},
        ],
        "controls": [
            {
                "id": str(control.id),
                "number": control.number,
                "title": control.title,
                "description": control.description,
                "safeguards": [
                    {
                        "id": safeguard.code,
                        "uuid": str(safeguard.id),
                        "title": safeguard.title,
                        "description": safeguard.description,
                        "asset_class": safeguard.asset_class,
                        "security_function": safeguard.security_function,
                        "ig": safeguard.ig,
                        "is_custom": safeguard.is_custom,
                    }
                    for safeguard in control.safeguards
                ],
            }
            for control in framework.controls
        ],
        "safeguard_count": sum(len(control.safeguards) for control in framework.controls),
    }


def import_from_file(
    db: Session,
    key: str = "cis",
    version: str = "v8.1.2",
    created_by_id: uuid.UUID | None = None,
) -> Framework:
    """Load the extracted JSON into the database as a published version (idempotent)."""
    existing = db.scalar(select(Framework).where(Framework.key == key, Framework.version == version))
    if existing is not None:
        return existing

    data = load_framework(key, version)
    framework = Framework(
        key=key,
        version=data.get("version", version),
        title=data.get("title", f"{key} {version}"),
        source=data.get("source", ""),
        status=FrameworkStatus.published,
        published_at=datetime.now(timezone.utc),
        created_by_id=created_by_id,
    )
    db.add(framework)
    db.flush()

    for index, control in enumerate(data["controls"]):
        row = FrameworkControl(
            framework_id=framework.id,
            number=control["number"],
            title=control["title"] or "",
            description=control["description"] or "",
            position=index,
        )
        db.add(row)
        db.flush()
        for offset, safeguard in enumerate(control["safeguards"]):
            db.add(
                FrameworkSafeguard(
                    framework_id=framework.id,
                    control_id=row.id,
                    code=safeguard["id"],
                    title=safeguard["title"] or "",
                    description=safeguard["description"] or "",
                    asset_class=safeguard["asset_class"] or "",
                    security_function=safeguard["security_function"] or "",
                    ig=safeguard["ig"],
                    position=offset,
                )
            )
    db.flush()
    return framework


def clone(db: Session, source: Framework, version: str, created_by_id: uuid.UUID | None) -> Framework:
    """Copy a version into a fresh draft, which is what editing a published one does."""
    draft = Framework(
        key=source.key,
        version=version,
        title=source.title,
        source=source.source,
        status=FrameworkStatus.draft,
        derived_from_id=source.id,
        created_by_id=created_by_id,
    )
    db.add(draft)
    db.flush()

    for control in source.controls:
        copy = FrameworkControl(
            framework_id=draft.id,
            number=control.number,
            title=control.title,
            description=control.description,
            position=control.position,
        )
        db.add(copy)
        db.flush()
        for safeguard in control.safeguards:
            db.add(
                FrameworkSafeguard(
                    framework_id=draft.id,
                    control_id=copy.id,
                    code=safeguard.code,
                    title=safeguard.title,
                    description=safeguard.description,
                    asset_class=safeguard.asset_class,
                    security_function=safeguard.security_function,
                    ig=safeguard.ig,
                    position=safeguard.position,
                    is_custom=safeguard.is_custom,
                )
            )
    db.flush()
    return draft
