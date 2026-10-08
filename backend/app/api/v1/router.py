from fastapi import APIRouter

from app.api.v1.routes import (
    admin,
    ai_settings,
    auth,
    class_modeler,
    diagrams,
    generation_pipelines,
    health,
    invitations,
    projects,
    search,
    srs,
    workspaces,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(ai_settings.router)
api_router.include_router(generation_pipelines.workspace_router)
api_router.include_router(generation_pipelines.router)
api_router.include_router(workspaces.router)
api_router.include_router(invitations.router)
api_router.include_router(projects.router)
api_router.include_router(diagrams.workspace_router)
api_router.include_router(diagrams.router)
api_router.include_router(class_modeler.router)
api_router.include_router(srs.workspace_router)
api_router.include_router(srs.router)
api_router.include_router(search.router)
api_router.include_router(admin.router)
