from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import current_user
from app.models import User
from app.template import DEFAULT_VERSION, load_template

router = APIRouter(prefix="/api/template", tags=["template"])


@router.get("")
def get_template(version: str = DEFAULT_VERSION, _: User = Depends(current_user)) -> dict:
    """The questionnaire definition the frontend renders: parts, questions, lists, X-grids."""
    try:
        return load_template(version)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown template version {version}") from None
