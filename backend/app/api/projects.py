from uuid import UUID
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import DomainError
from app.core.security import get_cipher
from app.database.session import get_session
from app.models import AuthorizedTarget, Credential, Environment, Project
from app.schemas.api import (
    CredentialCreate,
    CredentialRead,
    EnvironmentRead,
    ProjectCreate,
    ProjectRead,
    origin_of,
    target_origin,
)


router = APIRouter(prefix="/projects", tags=["projects"])


def project_response(project: Project) -> ProjectRead:
    origins = [target_origin(target.scheme, target.hostname, target.port) for target in project.authorized_targets]
    return ProjectRead(
        id=project.id,
        name=project.name,
        description=project.description,
        base_url=project.base_url,
        environment=project.environment,
        modality=project.modality,
        created_at=project.created_at,
        is_active=project.is_active,
        authorized_origins=sorted(origins),
        environments=[
            EnvironmentRead(id=env.id, name=env.name, base_url=env.base_url, is_active=env.is_active)
            for env in project.environments
        ],
    )


def find_project(session: Session, project_id: UUID) -> Project:
    project = session.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.authorized_targets), selectinload(Project.environments))
    )
    if project is None:
        raise DomainError(404, "project_not_found", "Project not found")
    return project


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> ProjectRead:
    project = Project(
        name=payload.name.strip(),
        description=payload.description,
        base_url=str(payload.base_url),
        environment=payload.environment,
        modality=payload.modality,
    )
    if not project.name:
        raise DomainError(422, "invalid_name", "Project name is required")
    project.environments.append(
        Environment(name=payload.environment, base_url=str(payload.base_url), is_active=True)
    )
    for url in payload.authorized_origins:
        parts = urlsplit(origin_of(url))
        project.authorized_targets.append(
            AuthorizedTarget(scheme=parts.scheme, hostname=parts.hostname or "", port=parts.port or 80)
        )
    session.add(project)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DomainError(409, "project_conflict", "Project could not be created") from None
    return project_response(find_project(session, project.id))


@router.get("", response_model=list[ProjectRead])
def list_projects(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> list[ProjectRead]:
    projects = session.scalars(
        select(Project)
        .options(selectinload(Project.authorized_targets), selectinload(Project.environments))
        .order_by(Project.created_at, Project.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [project_response(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: UUID, session: Session = Depends(get_session)) -> ProjectRead:
    return project_response(find_project(session, project_id))


@router.post("/{project_id}/credentials", response_model=CredentialRead)
def configure_credentials(
    project_id: UUID,
    payload: CredentialCreate,
    session: Session = Depends(get_session),
    cipher: Fernet = Depends(get_cipher),
) -> CredentialRead:
    project = find_project(session, project_id)
    allowed = {target_origin(target.scheme, target.hostname, target.port) for target in project.authorized_targets}
    if origin_of(payload.login_url) not in allowed:
        raise DomainError(422, "login_out_of_scope", "Login URL origin is not authorized")
    credential = session.scalar(select(Credential).where(Credential.project_id == project_id))
    if credential is None:
        credential = Credential(project_id=project_id)
        session.add(credential)
    credential.login_url = str(payload.login_url)
    credential.username_selector = payload.username_selector
    credential.password_selector = payload.password_selector
    credential.submit_selector = payload.submit_selector
    credential.success_selector = payload.success_selector
    credential.success_url_pattern = payload.success_url_pattern
    credential.username_ciphertext = cipher.encrypt(payload.username.get_secret_value().encode("utf-8"))
    credential.password_ciphertext = cipher.encrypt(payload.password.get_secret_value().encode("utf-8"))
    session.commit()
    session.refresh(credential)
    return CredentialRead(
        id=credential.id,
        project_id=credential.project_id,
        login_url=credential.login_url,
        auth_type=credential.auth_type,
        created_at=credential.created_at,
    )
