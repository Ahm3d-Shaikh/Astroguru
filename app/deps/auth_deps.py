from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from app.services.auth_service import get_user_by_id
from app.utils.admin import is_user_admin
from app.services.auth_service import JWT_SECRET, JWT_ALGO
import time

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Simple TTL cache: {user_id: (user_doc, expires_at)}
# 60-second TTL means a blocked/disabled user is locked out within 1 minute.
_USER_CACHE: dict = {}
_USER_CACHE_TTL = 60  # seconds


def _get_cached_user(user_id: str):
    entry = _USER_CACHE.get(user_id)
    if entry and entry[1] > time.monotonic():
        return entry[0]
    return None


def _set_cached_user(user_id: str, user: dict):
    _USER_CACHE[user_id] = (user, time.monotonic() + _USER_CACHE_TTL)


def invalidate_user_cache(user_id: str):
    """Call this whenever a user is blocked/unblocked/deleted."""
    _USER_CACHE.pop(user_id, None)


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid auth token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = _get_cached_user(user_id)
    if user is None:
        user = await get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user["_id"] = str(user["_id"])
        _set_cached_user(user_id, user)

    if not is_user_admin(user) and not user.get("is_enabled", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account Disabled")
    return user
