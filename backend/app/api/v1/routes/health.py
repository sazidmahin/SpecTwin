from fastapi import APIRouter


router = APIRouter()


@router.get("/health", summary="Backend health check")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
