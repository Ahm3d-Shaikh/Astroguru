from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from app.services.auth_service import get_user_by_id
from app.utils.admin import is_user_admin
from app.services.auth_service import JWT_SECRET, JWT_ALGO

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid auth token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not is_user_admin(user) and not user["is_enabled"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account Disabled")
    user["_id"] = str(user["_id"])
    return user
