"""Operational commands: `python -m app.cli init` and `python -m app.cli demo`."""

import sys

from sqlalchemy import select

from app import catalogue
from app.config import get_settings
from app.db import SessionLocal
from app.migrate import upgrade
from app.models import Client, Role, System, User
from app.security import hash_password


def init() -> None:
    """Bring the schema up to date, load the catalogue, create the admin."""
    upgrade()
    with SessionLocal() as db:
        catalogue.import_from_file(db)
        db.commit()
    settings = get_settings()
    with SessionLocal() as db:
        email = settings.admin_email.lower()
        if db.scalar(select(User).where(User.email == email)):
            print(f"admin {email} already exists")
            return
        db.add(
            User(
                email=email,
                full_name="Administrator",
                role=Role.admin,
                password_hash=hash_password(settings.admin_password),
            )
        )
        db.commit()
        print(f"created admin {email}")


def import_framework() -> None:
    """Load the extracted requirements catalogue into the database (idempotent)."""
    upgrade()
    with SessionLocal() as db:
        record = catalogue.import_from_file(db)
        db.commit()
        count = sum(len(control.safeguards) for control in record.controls)
        print(f"catalogue {record.key} {record.version}: {len(record.controls)} controls, {count} requirements")


def demo() -> None:
    """Two clients, a few systems and a consultant/respondent pair, for a first look."""
    init()
    with SessionLocal() as db:
        consultant = db.scalar(select(User).where(User.email == "consultant@example.com"))
        if consultant is None:
            consultant = User(
                email="consultant@example.com",
                full_name="Консультант",
                role=Role.consultant,
                password_hash=hash_password("consultant"),
            )
            db.add(consultant)
        respondent = db.scalar(select(User).where(User.email == "owner@example.com"))
        if respondent is None:
            respondent = User(
                email="owner@example.com",
                full_name="Владелец системы",
                role=Role.respondent,
                password_hash=hash_password("owner"),
            )
            db.add(respondent)

        for client_name, systems in {
            "ООО «Ромашка»": ["1С: Бухгалтерия", "CRM для продаж"],
            "АО «Василёк»": ["WMS склада", "Корпоративная почта"],
        }.items():
            client = db.scalar(select(Client).where(Client.name == client_name))
            if client is None:
                client = Client(name=client_name)
                db.add(client)
                db.flush()
            for system_name in systems:
                exists = db.scalar(
                    select(System).where(System.client_id == client.id, System.name == system_name)
                )
                if exists is None:
                    db.add(System(client_id=client.id, name=system_name))
            if client not in consultant.clients:
                consultant.clients.append(client)
            if client not in respondent.clients:
                respondent.clients.append(client)
        db.commit()
        print("demo data ready: consultant@example.com/consultant, owner@example.com/owner")


COMMANDS = {
    "migrate": lambda: (upgrade(), print("schema is up to date"))[-1],
    "init": init,
    "import-framework": import_framework,
    "demo": demo,
}

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "init"
    if name not in COMMANDS:
        sys.exit(f"unknown command {name}; expected one of {', '.join(COMMANDS)}")
    COMMANDS[name]()
