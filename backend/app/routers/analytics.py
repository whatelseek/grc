import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import analytics
from app.cis_scoring import compute as compute_cis
from app.db import get_db
from app.deps import current_user, get_client_for_user, scoped_surveys, visible_client_ids
from app.models import Assessment, Survey, SurveyResult, System, User

# The CIS controls that decide whether a recovery objective is achievable at all.
RECOVERY_CONTROLS = {"11": "Data Recovery", "17": "Incident Response Management"}

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
def portfolio(
    client_id: uuid.UUID | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregates over every survey the caller may see, optionally one client's."""
    stmt = scoped_surveys(db, user)
    if client_id is not None:
        get_client_for_user(db, user, client_id)
        stmt = stmt.where(System.client_id == client_id)
    surveys = list(db.scalars(stmt.order_by(Survey.updated_at.desc())))
    rows = [(survey, db.get(SurveyResult, survey.id)) for survey in surveys]
    payload = analytics.build(rows)
    payload["recovery_controls"] = _recovery_controls(db, user, client_id)
    return payload


def _recovery_controls(db: Session, user: User, client_id: uuid.UUID | None) -> list[dict]:
    """How well controls 11 and 17 are implemented — the ones an RTO/RPO gap rests on."""
    stmt = select(Assessment).order_by(Assessment.updated_at.desc())
    if client_id is not None:
        stmt = stmt.where(Assessment.client_id == client_id)
    else:
        allowed = visible_client_ids(db, user)
        if allowed is not None:
            stmt = stmt.where(Assessment.client_id.in_(allowed or [uuid.uuid4()]))

    seen: set[uuid.UUID] = set()
    out: list[dict] = []
    for assessment in db.scalars(stmt):
        # One row per client: its most recent assessment.
        if assessment.client_id in seen:
            continue
        seen.add(assessment.client_id)
        result = compute_cis(
            assessment.items,
            assessment.target_ig,
            assessment.framework,
            assessment.framework_version,
        )
        by_control = {row["control"]: row for row in result["by_control"]}
        out.append(
            {
                "assessment_id": str(assessment.id),
                "client_id": str(assessment.client_id),
                "client_name": assessment.client.name,
                "target_ig": assessment.target_ig,
                "controls": [
                    {
                        "control": number,
                        "title": title,
                        "implementation": (by_control.get(number) or {}).get("implementation"),
                        "not_implemented": (by_control.get(number) or {}).get("not_implemented", 0),
                    }
                    for number, title in RECOVERY_CONTROLS.items()
                ],
            }
        )
    return out
