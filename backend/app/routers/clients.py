import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import (
    current_user,
    get_client_for_user,
    get_system_for_user,
    require_editor,
    visible_client_ids,
)
from app.models import Client, System, User
from app.schemas import (
    ClientCreate,
    ClientOut,
    ClientUpdate,
    SystemCreate,
    SystemOut,
    SystemUpdate,
)

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.get("", response_model=list[ClientOut])
def list_clients(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[ClientOut]:
    """The client picker: every client the signed-in user is allowed to work on."""
    counts = dict(
        db.execute(select(System.client_id, func.count(System.id)).group_by(System.client_id)).all()
    )
    stmt = select(Client).order_by(Client.name)
    allowed = visible_client_ids(db, user)
    if allowed is not None:
        stmt = stmt.where(Client.id.in_(allowed or [uuid.uuid4()]))
    return [
        ClientOut(
            id=c.id,
            name=c.name,
            code=c.code,
            notes=c.notes,
            is_active=c.is_active,
            system_count=counts.get(c.id, 0),
        )
        for c in db.scalars(stmt)
    ]


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate, actor: User = Depends(require_editor), db: Session = Depends(get_db)
) -> ClientOut:
    if db.scalar(select(Client).where(Client.name == payload.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Client with this name already exists")
    client = Client(**payload.model_dump())
    db.add(client)
    # A consultant who creates a client keeps access to it.
    if actor.role.value == "consultant":
        actor.clients.append(client)
    db.commit()
    return ClientOut(
        id=client.id,
        name=client.name,
        code=client.code,
        notes=client.notes,
        is_active=client.is_active,
    )


@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> ClientOut:
    client = get_client_for_user(db, user, client_id)
    return ClientOut(
        id=client.id,
        name=client.name,
        code=client.code,
        notes=client.notes,
        is_active=client.is_active,
        system_count=len(client.systems),
    )


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdate,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
) -> ClientOut:
    client = get_client_for_user(db, user, client_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(client, field, value)
    db.commit()
    return ClientOut(
        id=client.id,
        name=client.name,
        code=client.code,
        notes=client.notes,
        is_active=client.is_active,
        system_count=len(client.systems),
    )


@router.get("/{client_id}/systems", response_model=list[SystemOut])
def list_systems(
    client_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[SystemOut]:
    client = get_client_for_user(db, user, client_id)
    return [
        SystemOut(
            id=s.id,
            client_id=s.client_id,
            name=s.name,
            business_owner=s.business_owner,
            it_owner=s.it_owner,
            description=s.description,
            survey_count=len(s.surveys),
        )
        for s in sorted(client.systems, key=lambda s: s.name)
    ]


@router.post("/{client_id}/systems", response_model=SystemOut, status_code=status.HTTP_201_CREATED)
def create_system(
    client_id: uuid.UUID,
    payload: SystemCreate,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
) -> SystemOut:
    get_client_for_user(db, user, client_id)
    exists = db.scalar(
        select(System).where(System.client_id == client_id, System.name == payload.name)
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "System with this name already exists")
    system = System(client_id=client_id, **payload.model_dump())
    db.add(system)
    db.commit()
    return SystemOut(
        id=system.id,
        client_id=system.client_id,
        name=system.name,
        business_owner=system.business_owner,
        it_owner=system.it_owner,
        description=system.description,
    )


systems_router = APIRouter(prefix="/api/systems", tags=["systems"])


@systems_router.patch("/{system_id}", response_model=SystemOut)
def update_system(
    system_id: uuid.UUID,
    payload: SystemUpdate,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
) -> SystemOut:
    system = get_system_for_user(db, user, system_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(system, field, value)
    db.commit()
    return SystemOut(
        id=system.id,
        client_id=system.client_id,
        name=system.name,
        business_owner=system.business_owner,
        it_owner=system.it_owner,
        description=system.description,
        survey_count=len(system.surveys),
    )


@systems_router.delete("/{system_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_system(
    system_id: uuid.UUID,
    user: User = Depends(require_editor),
    db: Session = Depends(get_db),
) -> None:
    system = get_system_for_user(db, user, system_id)
    db.delete(system)
    db.commit()
