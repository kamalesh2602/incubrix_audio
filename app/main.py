from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import setup_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure storage directory exists
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# Setup consistent JSON error formatting for validation, 404, and app errors
setup_exception_handlers(app)

# Include v1 API routes
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    return {"status": "ready"}
