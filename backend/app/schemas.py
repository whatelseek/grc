import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import (
    AssessmentStatus,
    FrameworkStatus,
    ImplementationStatus,
    Priority,
    Role,
    SurveyStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    client_ids: list[uuid.UUID] = Field(default_factory=list)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = ""
    role: Role = Role.respondent
    client_ids: list[uuid.UUID] = Field(default_factory=list)


class UserUpdate(BaseModel):
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=6)
    role: Role | None = None
    is_active: bool | None = None
    client_ids: list[uuid.UUID] | None = None


class ClientBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str | None = None
    notes: str = ""


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class ClientOut(ORMModel):
    id: uuid.UUID
    name: str
    code: str | None
    notes: str
    is_active: bool
    system_count: int = 0


class SystemBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    business_owner: str = ""
    it_owner: str = ""
    description: str = ""


class SystemCreate(SystemBase):
    pass


class SystemUpdate(BaseModel):
    name: str | None = None
    business_owner: str | None = None
    it_owner: str | None = None
    description: str | None = None


class SystemOut(ORMModel):
    id: uuid.UUID
    client_id: uuid.UUID
    name: str
    business_owner: str
    it_owner: str
    description: str
    survey_count: int = 0


class AnswerIn(BaseModel):
    question_code: int
    text: str | None = None
    level: str | None = None
    selections: list[str] | None = None


class AnswerOut(ORMModel):
    question_code: int
    text: str | None
    level: str | None
    selections: list[str] | None


class SurveyCreate(BaseModel):
    system_id: uuid.UUID
    assignee_id: uuid.UUID | None = None


class SurveyOut(ORMModel):
    id: uuid.UUID
    system_id: uuid.UUID
    system_name: str | None = None
    client_id: uuid.UUID | None = None
    client_name: str | None = None
    status: SurveyStatus
    template_version: str
    assignee_id: uuid.UUID | None
    updated_at: datetime
    submitted_at: datetime | None


class ResultOut(BaseModel):
    overall_criticality: float | None
    criticality_by_type: dict
    mtpd_hours: float | None
    mtpd_beyond_scale: bool = False
    rto_hours: float | None
    rpo_hours: float | None
    issues: list[dict]
    progress: dict


class SurveyDetail(SurveyOut):
    answers: list[AnswerOut]
    result: ResultOut


class AnswersPatch(BaseModel):
    answers: list[AnswerIn]


class DashboardRow(BaseModel):
    survey_id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    system_id: uuid.UUID
    system_name: str
    business_owner: str
    it_owner: str
    status: SurveyStatus
    overall_criticality: float | None
    mtpd_hours: float | None
    rto_hours: float | None
    rpo_hours: float | None
    stated_mtpd: str | None
    stated_rto: str | None
    stated_rpo: str | None
    current_rto: str | None
    current_rpo: str | None
    required_filled: int
    required_total: int
    warnings: int
    updated_at: datetime


class AssessmentCreate(BaseModel):
    client_id: uuid.UUID
    name: str = ""
    target_ig: int = Field(default=1, ge=1, le=3)
    assessor_id: uuid.UUID | None = None
    # Defaults to the current published catalogue version.
    framework_id: uuid.UUID | None = None


class AssessmentUpdate(BaseModel):
    name: str | None = None
    target_ig: int | None = Field(default=None, ge=1, le=3)
    status: AssessmentStatus | None = None
    assessor_id: uuid.UUID | None = None


class EvidenceOut(ORMModel):
    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime


class ItemIn(BaseModel):
    safeguard_id: str
    status: ImplementationStatus | None = None
    owner: str | None = None
    due_date: date | None = None
    priority: Priority | None = None
    notes: str | None = None


class ItemOut(ORMModel):
    safeguard_id: str
    status: ImplementationStatus
    owner: str
    due_date: date | None
    priority: Priority | None
    notes: str
    evidence: list[EvidenceOut] = Field(default_factory=list)


class ItemsPatch(BaseModel):
    items: list[ItemIn]


class AssessmentOut(ORMModel):
    id: uuid.UUID
    client_id: uuid.UUID
    client_name: str | None = None
    framework: str
    framework_version: str
    framework_id: uuid.UUID | None = None
    name: str
    target_ig: int
    status: AssessmentStatus
    assessor_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    implementation: float | None = None
    gaps_open: int = 0


class AssessmentDetail(AssessmentOut):
    items: list[ItemOut]
    result: dict


class FrameworkOut(ORMModel):
    id: uuid.UUID
    key: str
    version: str
    title: str
    source: str
    status: FrameworkStatus
    notes: str
    derived_from_id: uuid.UUID | None
    created_at: datetime
    published_at: datetime | None
    control_count: int = 0
    safeguard_count: int = 0
    custom_count: int = 0
    assessments_using: int = 0


class FrameworkDraftIn(BaseModel):
    version: str = Field(min_length=1, max_length=40)
    notes: str = ""


class FrameworkUpdate(BaseModel):
    title: str | None = None
    version: str | None = Field(default=None, min_length=1, max_length=40)
    notes: str | None = None
    source: str | None = None


class ControlIn(BaseModel):
    number: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    position: int | None = None


class ControlUpdate(BaseModel):
    number: str | None = None
    title: str | None = None
    description: str | None = None
    position: int | None = None


class SafeguardIn(BaseModel):
    control_id: uuid.UUID
    code: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=400)
    description: str = ""
    asset_class: str = ""
    security_function: str = ""
    ig: int = Field(default=1, ge=1, le=3)
    position: int | None = None


class SafeguardUpdate(BaseModel):
    code: str | None = None
    title: str | None = None
    description: str | None = None
    asset_class: str | None = None
    security_function: str | None = None
    ig: int | None = Field(default=None, ge=1, le=3)
    position: int | None = None


class MigrateIn(BaseModel):
    framework_id: uuid.UUID
