import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import analytics
from app.db import get_db
from app.deps import current_user, get_client_for_user, scoped_surveys
from app.models import Survey, SurveyResult, System, User

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
    return analytics.build(rows)
