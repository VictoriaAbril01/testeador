"""Schema checks against the configured PostgreSQL database.

Tests require the initial migration and roll back all inserted rows.
"""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.config import get_database_url
from app.models import AuthorizedTarget, Finding, Project, TestRun as RunModel


@pytest.fixture(scope="module")
def engine():
    db_engine = create_engine(get_database_url())
    try:
        yield db_engine
    finally:
        db_engine.dispose()


def test_initial_migration_created_all_entities(engine):
    tables = set(inspect(engine).get_table_names())
    assert {
        "projects",
        "authorized_targets",
        "environments",
        "credentials",
        "test_runs",
        "discovered_pages",
        "test_steps",
        "findings",
        "evidence",
        "alembic_version",
    } <= tables


def test_authorized_scope_and_finding_uniqueness(engine):
    connection = engine.connect()
    transaction = connection.begin()
    try:
        session = Session(bind=connection)
        project = Project(
            name="Migration test",
            base_url="https://example.test/",
            environment="staging",
            modality="blackbox",
        )
        session.add(project)
        session.flush()

        target = AuthorizedTarget(
            project_id=project.id,
            scheme="https",
            hostname="example.test",
            port=443,
        )
        session.add(target)
        run = RunModel(
            project_id=project.id,
            max_pages=5,
            max_depth=2,
            max_requests=50,
            max_concurrency=1,
            page_timeout_ms=10000,
            execution_timeout_ms=60000,
        )
        session.add(run)
        session.flush()

        assert session.scalar(select(AuthorizedTarget).where(AuthorizedTarget.project_id == project.id)) is target
        assert run.status == "pending"

        finding = Finding(
            run_id=run.id,
            fingerprint="a" * 64,
            error_type="javascript",
            severity="medium",
            description="Observed page error",
            observed_result="An exception was observed",
        )
        session.add(finding)
        session.flush()

        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.add(
                    Finding(
                        run_id=run.id,
                        fingerprint="a" * 64,
                        error_type="javascript",
                        severity="medium",
                        description="Duplicate",
                        observed_result="Same error",
                    )
                )
                session.flush()

        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.add(
                    AuthorizedTarget(
                        project_id=project.id,
                        scheme="https",
                        hostname="example.test",
                        port=70000,
                    )
                )
                session.flush()

        assert session.scalar(select(Finding).where(Finding.id == finding.id)) is finding
        session.close()
    finally:
        transaction.rollback()
        connection.close()


def test_run_requires_existing_project(engine):
    connection = engine.connect()
    transaction = connection.begin()
    try:
        with Session(bind=connection) as session:
            with pytest.raises(IntegrityError):
                with session.begin_nested():
                    session.add(
                        RunModel(
                            project_id=uuid4(),
                            max_pages=1,
                            max_depth=0,
                            max_requests=1,
                            max_concurrency=1,
                            page_timeout_ms=1000,
                            execution_timeout_ms=1000,
                        )
                    )
                    session.flush()
    finally:
        transaction.rollback()
        connection.close()
