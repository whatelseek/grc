"""Programmatic access to the Alembic migrations (used by the CLI and the tests)."""

from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return config


def upgrade(revision: str = "head") -> None:
    command.upgrade(alembic_config(), revision)
