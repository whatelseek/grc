import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
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


class AssessmentStatus(str, enum.Enum):
    draft = "draft"
    in_progress = "in_progress"
    completed = "completed"


class ImplementationStatus(str, enum.Enum):
    """How far a CIS safeguard is implemented. `not_applicable` leaves the score alone."""

    not_implemented = "not_implemented"
    partial = "partial"
    implemented = "implemented"
    not_applicable = "not_applicable"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


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


class Assessment(Base):
    """One CIS Controls assessment of a client, as of a date."""

    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    framework: Mapped[str] = mapped_column(String(40), default="cis")
    framework_version: Mapped[str] = mapped_column(String(20), default="v8.1.2")
    name: Mapped[str] = mapped_column(String(200), default="")
    # The group the client is aiming for; safeguards above it are out of scope.
    target_ig: Mapped[int] = mapped_column(default=1)
    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(AssessmentStatus, name="assessment_status"), default=AssessmentStatus.draft
    )
    assessor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped[Client] = relationship()
    assessor: Mapped[User | None] = relationship(foreign_keys=[assessor_id])
    items: Mapped[list["AssessmentItem"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan", lazy="selectin"
    )


class AssessmentItem(Base):
    """The verdict on one safeguard, plus what it takes to close it."""

    __tablename__ = "assessment_items"
    __table_args__ = (
        UniqueConstraint("assessment_id", "safeguard_id", name="uq_items_assessment_safeguard"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), index=True
    )
    safeguard_id: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[ImplementationStatus] = mapped_column(
        Enum(ImplementationStatus, name="implementation_status"),
        default=ImplementationStatus.not_implemented,
    )
    owner: Mapped[str] = mapped_column(String(200), default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[Priority | None] = mapped_column(
        Enum(Priority, name="remediation_priority"), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    assessment: Mapped[Assessment] = relationship(back_populates="items")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", lazy="selectin"
    )


class Evidence(Base):
    """A file backing up a verdict. The bytes live on disk; this row is the index."""

    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = _uuid_pk()
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_items.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    stored_name: Mapped[str] = mapped_column(String(80))
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped[AssessmentItem] = relationship(back_populates="evidence")
    uploaded_by: Mapped[User | None] = relationship(foreign_keys=[uploaded_by_id])
