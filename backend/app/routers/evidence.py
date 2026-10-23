import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import evidence as storage
from app.db import get_db
from app.deps import current_user, get_client_for_user
from app.frameworks import safeguards
from app.models import Assessment, AssessmentItem, AssessmentStatus, Evidence, User
from app.schemas import EvidenceOut

router = APIRouter(prefix="/api", tags=["evidence"])


def _item_for_user(db: Session, user: User, assessment_id: uuid.UUID, safeguard_id: str) -> AssessmentItem:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Оценка не найдена")
    get_client_for_user(db, user, assessment.client_id)
    if safeguard_id not in safeguards(assessment.framework, assessment.framework_version):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Нет меры защиты {safeguard_id}")

    item = next((i for i in assessment.items if i.safeguard_id == safeguard_id), None)
    if item is None:
        # Attaching evidence is itself an answer, so the row is created on demand.
        item = AssessmentItem(assessment_id=assessment.id, safeguard_id=safeguard_id)
        db.add(item)
        assessment.items.append(item)
        db.flush()
    if assessment.status is AssessmentStatus.completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Оценка завершена и закрыта для правок")
    return item


@router.post(
    "/assessments/{assessment_id}/items/{safeguard_id}/evidence",
    response_model=EvidenceOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_evidence(
    assessment_id: uuid.UUID,
    safeguard_id: str,
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> EvidenceOut:
    item = _item_for_user(db, user, assessment_id, safeguard_id)
    stored_name, content_type, size = storage.save(file)
    record = Evidence(
        item_id=item.id,
        filename=storage.clean_filename(file.filename),
        content_type=content_type,
        size_bytes=size,
        stored_name=stored_name,
        uploaded_by_id=user.id,
    )
    db.add(record)
    db.commit()
    return EvidenceOut.model_validate(record)


def _evidence_for_user(db: Session, user: User, evidence_id: uuid.UUID) -> Evidence:
    record = db.get(Evidence, evidence_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл не найден")
    assessment = db.get(Assessment, record.item.assessment_id)
    get_client_for_user(db, user, assessment.client_id)
    return record


@router.get("/evidence/{evidence_id}")
def download_evidence(
    evidence_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> FileResponse:
    record = _evidence_for_user(db, user, evidence_id)
    path = storage.path_for(record.stored_name)
    if not path.exists():
        raise HTTPException(status.HTTP_410_GONE, "Файл больше не доступен в хранилище")
    return FileResponse(path, media_type=record.content_type, filename=record.filename)


@router.delete("/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence(
    evidence_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> None:
    record = _evidence_for_user(db, user, evidence_id)
    stored_name = record.stored_name
    db.delete(record)
    db.commit()
    storage.remove(stored_name)
