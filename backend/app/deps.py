import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_db

bearer = HTTPBearer(auto_error=False)


def _encode(sub: str, minutes: int = 60, days: int = 0) -> str:
    exp = datetime.now(timezone.utc) + (timedelta(days=days) if days else timedelta(minutes=minutes))
    return jwt.encode({"sub": sub, "exp": exp, "jti": str(uuid.uuid4())}, settings.JWT_SECRET, algorithm="HS256")


def issue_pair(user_id: str) -> tuple[str, str]:
    return (
        _encode(user_id, minutes=settings.JWT_EXP_MIN),
        _encode(user_id, days=settings.REFRESH_EXP_DAYS),
    )


def decode_sub(token: str) -> str:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])["sub"]
    except (JWTError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    return decode_sub(creds.credentials)
