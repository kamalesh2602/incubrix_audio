from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []


class NotFoundError(AppException):
    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ValidationAppError(AppException):
    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            details=details,
        )


def format_error_response(code: str, message: str, details: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        }
    }


def setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            loc = err.get("loc", [])
            # Skip 'body' in location to make field names clean and readable
            field_parts = [str(part) for part in loc if part != "body"]
            field = ".".join(field_parts) if field_parts else "body"
            details.append({
                "field": field,
                "message": err.get("msg", "Invalid value"),
                "type": err.get("type", "value_error"),
            })

        status_code = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        return JSONResponse(
            status_code=status_code,
            content=format_error_response(
                code="VALIDATION_ERROR",
                message="Request validation failed. Please check the provided fields.",
                details=details,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            422: "VALIDATION_ERROR",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=format_error_response(
                code=code,
                message=detail_msg,
                details=[],
            ),
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content=format_error_response(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            ),
        )
