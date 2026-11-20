from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, RevokedToken
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    import jwt
    from .config import settings
    payload=jwt.decode(creds.credentials,settings.jwt_secret,algorithms=[settings.jwt_algorithm])
    if db.get(RevokedToken,payload.get('jti','')):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,"Session has been logged out")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user
