import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import setup_exception_handlers
from app.core.logging import get_correlation_id, set_correlation_id, setup_logging

logger = logging.getLogger("app.access")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Extract or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID")
        if not correlation_id or not correlation_id.strip():
            correlation_id = str(uuid.uuid4())
        else:
            correlation_id = correlation_id.strip()

        set_correlation_id(correlation_id)
        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                f"Unhandled exception processing {request.method} {request.url.path}: {exc}",
                exc_info=True,
                extra={"method": request.method, "path": request.url.path, "duration_ms": duration_ms},
            )
            raise exc

        duration_ms = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Correlation-ID"] = correlation_id

        # Log completion in structured JSON
        logger.info(
            f"{request.method} {request.url.path} {response.status_code} ({duration_ms}ms)",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else None,
            },
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize structured JSON logging
    setup_logging(settings.LOG_LEVEL)
    # Ensure local storage directory exists
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# Setup middleware
app.add_middleware(CorrelationIdMiddleware)

# Setup consistent JSON error formatting for validation, 404, and app errors
setup_exception_handlers(app)

# Include v1 API routes
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", summary="Health Check", description="Returns liveness probe status.")
async def health():
    return {"status": "ok"}


@app.get("/ready", summary="Readiness Check", description="Returns readiness status.")
async def ready():
    # Verify local storage accessibility
    try:
        settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        test_probe = settings.STORAGE_DIR / ".ready_probe"
        test_probe.write_text("ok", encoding="utf-8")
        test_probe.unlink(missing_ok=True)
    except Exception as exc:
        logger.error(f"Readiness probe failed on storage write: {exc}")
        return {"status": "not_ready", "error": str(exc)}

    return {"status": "ready"}
