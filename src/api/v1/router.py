from fastapi import APIRouter
from src.api.v1.auth.routes import router as auth_router
from src.api.v1.analysis.routes import router as analysis_router
from src.api.v1.user.routes import router as user_router
from src.api.v1.scribe.routes import router as scribe_router
from src.api.v1.research.routes import router as research_router
from src.api.v1.taida.routes import router as taida_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(analysis_router)
api_router.include_router(user_router)
api_router.include_router(scribe_router)
api_router.include_router(research_router)
api_router.include_router(taida_router)
