from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.project_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    def readiness_check() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": settings.project_name, "health": f"{settings.api_v1_prefix}/health"}

    return app


app = create_app()

