from fastapi import APIRouter

from app.api.v1.endpoints.jobs import router as jobs_router
from app.api.v1.endpoints.music import router as music_router

api_v1_router = APIRouter()
api_v1_router.include_router(music_router, tags=["music"])
api_v1_router.include_router(jobs_router, tags=["jobs"])
