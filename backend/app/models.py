import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Role(str, enum.Enum):
    admin = "admin"
    consultant = "consultant"
    respondent = "respondent"


class SurveyStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    reviewed = "reviewed"


user_clients = Table(
    "user_clients",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("client_id", UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), default=Role.respondent)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    clients: Mapped[list["Client"]] = relationship(secondary=user_clients, back_populates="users")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200), unique=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list[User]] = relationship(secondary=user_clients, back_populates="clients")
    systems: Mapped[list["System"]] = relationship(back_populates="client", cascade="all, delete-orphan")


class System(Base):
    __tablename__ = "systems"
    __table_args__ = (UniqueConstraint("client_id", "name", name="uq_systems_client_name"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    business_owner: Mapped[str] = mapped_column(String(200), default="")
    it_owner: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client: Mapped[Client] = relationship(back_populates="systems")
    surveys: Mapped[list["Survey"]] = relationship(back_populates="system", cascade="all, delete-orphan")


class Survey(Base):
    """One filled-in questionnaire for one system (the Excel file's replacement)."""

    __tablename__ = "surveys"

    id: Mapped[uuid.UUID] = _uuid_pk()
    system_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("systems.id", ondelete="CASCADE"), index=True)
    template_version: Mapped[str] = mapped_column(String(20), default="v1")
    status: Mapped[SurveyStatus] = mapped_column(
        Enum(SurveyStatus, name="survey_status"), default=SurveyStatus.draft
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    system: Mapped[System] = relationship(back_populates="surveys")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    answers: Mapped[list["Answer"]] = relationship(
        back_populates="survey", cascade="all, delete-orphan", lazy="selectin"
    )
    result: Mapped["SurveyResult | None"] = relationship(
        back_populates="survey", cascade="all, delete-orphan", uselist=False
    )


class Answer(Base):
    """One answer cell. `level` holds the X-grid choice, `text` free text, `selections` multi-pick."""

    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("survey_id", "question_code", name="uq_answers_survey_question"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    survey_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    question_code: Mapped[int] = mapped_column(index=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    selections: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    survey: Mapped[Survey] = relationship(back_populates="answers")


class SurveyResult(Base):
    """Snapshot of the scoring engine output, refreshed on every save."""

    __tablename__ = "survey_results"

    survey_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), primary_key=True
    )
    overall_criticality: Mapped[float | None] = mapped_column(Float, nullable=True)
    criticality_by_type: Mapped[dict] = mapped_column(JSONB, default=dict)
    mtpd_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    rto_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    rpo_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    issues: Mapped[list] = mapped_column(JSONB, default=list)
    progress: Mapped[dict] = mapped_column(JSONB, default=dict)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    survey: Mapped[Survey] = relationship(back_populates="result")
