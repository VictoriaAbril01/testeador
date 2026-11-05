import hmac

from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.settings import Settings, get_settings


bearer = HTTPBearer(auto_error=False)


def require_operator(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> None:
    supplied = credentials.credentials if credentials else ""
    expected = settings.testlab_api_key.get_secret_value()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_cipher(settings: Settings = Depends(get_settings)) -> Fernet:
    return Fernet(settings.testlab_fernet_key.get_secret_value().encode("ascii"))
