"""Storage for evidence files.

The bytes go to a directory on a mounted volume under a generated name; the original
filename is kept in the database only. A client never sees a path, so an uploaded name
cannot reach the filesystem.
"""

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

# Formats an auditor actually attaches: documents, spreadsheets, screenshots, exports.
ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/json": ".json",
    "application/zip": ".zip",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
}
_SAFE_NAME = re.compile(r"[^\w\s.()\[\]-]", re.UNICODE)


def storage_dir() -> Path:
    path = Path(get_settings().evidence_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_filename(name: str | None) -> str:
    base = Path(name or "файл").name
    cleaned = _SAFE_NAME.sub("_", base).strip() or "файл"
    return cleaned[:255]


def save(upload: UploadFile) -> tuple[str, str, int]:
    """Store the upload and return (stored_name, content_type, size)."""
    content_type = (upload.content_type or "").split(";")[0].strip()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Тип файла {content_type or 'неизвестен'} не поддерживается. "
            "Допустимы PDF, изображения, документы Office, CSV, TXT, JSON и ZIP.",
        )

    limit = get_settings().evidence_max_bytes
    stored_name = f"{uuid.uuid4().hex}{ALLOWED_TYPES[content_type]}"
    target = storage_dir() / stored_name
    size = 0
    try:
        with target.open("wb") as fh:
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        f"Файл больше {limit // (1024 * 1024)} МБ",
                    )
                fh.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if size == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файл пустой")
    return stored_name, content_type, size


def path_for(stored_name: str) -> Path:
    # Guard against a stored name that somehow carries a path separator.
    return storage_dir() / Path(stored_name).name


def remove(stored_name: str) -> None:
    path_for(stored_name).unlink(missing_ok=True)
