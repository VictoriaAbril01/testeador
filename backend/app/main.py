from contextlib import asynccontextmanager
import asyncio

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.executions import router as executions_router
from app.api.projects import router as projects_router
from app.api.incidents import router as incidents_router
from app.api.dashboard import router as dashboard_router
from app.core.errors import (
    DomainError,
    database_error_handler,
    domain_error_handler,
    validation_error_handler,
)
from app.core.security import require_operator
from app.core.settings import get_settings
from app.database.session import get_engine
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from app.services.evidence import purge_expired
from app.services.recovery import reconcile_once
from app.services.queue import connection as redis_connection


async def evidence_maintenance() -> None:
    while True:
        try:
            await asyncio.to_thread(_purge_evidence)
        except Exception:
            # Maintenance failure cannot expose storage paths or stop request handling.
            pass
        await asyncio.sleep(3600)


def _purge_evidence() -> None:
    with Session(get_engine()) as session:
        purge_expired(session)


async def execution_maintenance() -> None:
    while True:
        try:
            await asyncio.to_thread(_reconcile_executions)
        except Exception:
            # Redis outages must not make the API claim that a job has finished.
            pass
        await asyncio.sleep(5)


def _reconcile_executions() -> None:
    with Session(get_engine()) as session:
        reconcile_once(session, redis_connection())


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    Fernet(settings.testlab_fernet_key.get_secret_value().encode("ascii"))
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    maintenance = asyncio.create_task(evidence_maintenance())
    execution_recovery = asyncio.create_task(execution_maintenance())
    try:
        yield
    finally:
        maintenance.cancel()
        execution_recovery.cancel()
        try:
            await maintenance
        except asyncio.CancelledError:
            pass
        try:
            await execution_recovery
        except asyncio.CancelledError:
            pass
    get_engine().dispose()


app = FastAPI(title="TestLab API", version="0.1.0", lifespan=lifespan)
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(SQLAlchemyError, database_error_handler)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}


api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_operator)])
api_router.include_router(projects_router)
api_router.include_router(executions_router)
api_router.include_router(dashboard_router)
api_router.include_router(incidents_router)
app.include_router(api_router)
