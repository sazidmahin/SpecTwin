from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_workspace_membership, get_db
from app.db.models import WorkspaceMember
from app.services.search_service import search_workspace

router = APIRouter(prefix="/workspaces/{workspace_id}/search", tags=["search"])


@router.get("")
def search(
    q: str = Query(default="", max_length=200),
    membership: WorkspaceMember = Depends(get_current_workspace_membership),
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, Any]]]:
    return search_workspace(db, membership=membership, query=q)
