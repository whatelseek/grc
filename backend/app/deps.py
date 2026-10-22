"""Authentication and client-scoping dependencies.

Access rules:
  admin       — everything, including user management.
  consultant  — only the clients they are assigned to; full access to those clients' data.
  respondent  — only their assigned clients, and only surveys assigned to them.
"""

import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Client, Role, Survey, System, User

bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    from app.security import decode_access_token

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inactive or unknown user")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role is not Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


def require_editor(user: User = Depends(current_user)) -> User:
    """Admins and consultants may manage clients, systems and surveys."""
    if user.role not in (Role.admin, Role.consultant):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Consultant or admin role required")
    return user


def visible_client_ids(db: Session, user: User) -> list[uuid.UUID] | None:
    """None means "no restriction" (admin)."""
    if user.role is Role.admin:
        return None
    return [c.id for c in user.clients]


def get_client_for_user(db: Session, user: User, client_id: uuid.UUID) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")
    allowed = visible_client_ids(db, user)
    if allowed is not None and client.id not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Client not assigned to you")
    return client


def get_system_for_user(db: Session, user: User, system_id: uuid.UUID) -> System:
    system = db.get(System, system_id)
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "System not found")
    get_client_for_user(db, user, system.client_id)
    return system


def get_survey_for_user(db: Session, user: User, survey_id: uuid.UUID) -> Survey:
    survey = db.get(Survey, survey_id)
    if survey is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Survey not found")
    get_system_for_user(db, user, survey.system_id)
    if user.role is Role.respondent and survey.assignee_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Survey not assigned to you")
    return survey


def scoped_surveys(db: Session, user: User):
    """A select() over surveys the user may see, joined to system and client."""
    stmt = select(Survey).join(System).join(Client)
    allowed = visible_client_ids(db, user)
    if allowed is not None:
        stmt = stmt.where(Client.id.in_(allowed or [uuid.uuid4()]))
    if user.role is Role.respondent:
        stmt = stmt.where(Survey.assignee_id == user.id)
    return stmt
