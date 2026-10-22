import os
import uuid

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://bia:bia@localhost:5432/bia_test"
)
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-hs256")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Client, Role, System, User
from app.security import hash_password


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables(schema):
    with engine.begin() as conn:
        conn.execute(
            text(
                "truncate answers, survey_results, surveys, systems, user_clients, clients, users "
                "restart identity cascade"
            )
        )
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def make_user(db):
    def _make(role: Role, email: str | None = None, password: str = "secret123", clients=()):
        user = User(
            email=email or f"{role.value}-{uuid.uuid4().hex[:6]}@example.com",
            full_name=role.value,
            role=role,
            password_hash=hash_password(password),
        )
        user.clients = list(clients)
        db.add(user)
        db.commit()
        return user, password

    return _make


@pytest.fixture
def make_client_org(db):
    def _make(name: str | None = None):
        org = Client(name=name or f"Клиент {uuid.uuid4().hex[:6]}")
        db.add(org)
        db.commit()
        return org

    return _make


@pytest.fixture
def make_system(db):
    def _make(org, name: str | None = None):
        system = System(
            client_id=org.id,
            name=name or f"Система {uuid.uuid4().hex[:6]}",
            business_owner="Владелец",
            it_owner="ИТ",
        )
        db.add(system)
        db.commit()
        return system

    return _make


@pytest.fixture
def auth(client):
    def _auth(user, password="secret123"):
        response = client.post(
            "/api/auth/login", json={"email": user.email, "password": password}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _auth
