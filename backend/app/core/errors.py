from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError


class DomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic error details can contain the original input, including credentials.
    fields = [
        {"field": ".".join(str(part) for part in error["loc"]), "code": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid_request", "message": "Invalid request data", "fields": fields}},
    )


async def database_error_handler(_request: Request, _exc: SQLAlchemyError) -> JSONResponse:
    # SQLAlchemy exceptions can include bound values; never serialize them.
    return JSONResponse(
        status_code=503,
        content={"error": {"code": "database_unavailable", "message": "Database operation failed"}},
    )
