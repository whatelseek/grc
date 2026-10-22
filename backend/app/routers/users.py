import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, require_admin, require_editor, visible_client_ids
from app.models import Client, User
from app.schemas import UserCreate, UserOut, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        client_ids=[c.id for c in user.clients],
    )


def _assign_clients(db: Session, user: User, client_ids: list[uuid.UUID]) -> None:
    clients = list(db.scalars(select(Client).where(Client.id.in_(client_ids)))) if client_ids else []
    if len(clients) != len(set(client_ids)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown client id")
    user.clients = clients


@router.get("", response_model=list[UserOut])
def list_users(
    actor: User = Depends(require_editor), db: Session = Depends(get_db)
) -> list[UserOut]:
    """Consultants see users of their own clients, so they can pick an assignee."""
    users = list(db.scalars(select(User).order_by(User.email)))
    allowed = visible_client_ids(db, actor)
    if allowed is not None:
        allowed_set = set(allowed)
        users = [u for u in users if allowed_set & {c.id for c in u.clients}]
    return [_out(u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> UserOut:
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    _assign_clients(db, user, payload.client_ids)
    db.commit()
    return _out(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.password:
        user.password_hash = hash_password(payload.password)
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        if user.id == actor.id and not payload.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot deactivate yourself")
        user.is_active = payload.is_active
    if payload.client_ids is not None:
        _assign_clients(db, user, payload.client_ids)
    db.commit()
    return _out(user)


@router.get("/me/clients", response_model=list[uuid.UUID])
def my_clients(user: User = Depends(current_user)) -> list[uuid.UUID]:
    return [c.id for c in user.clients]
