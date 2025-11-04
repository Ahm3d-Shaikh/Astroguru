from fastapi import APIRouter, HTTPException, status
from app.models.login import AdminLoginRequest
from app.services.auth_service import get_user_by_email, verify_password, create_access_token
from app.db.mongo import db

router = APIRouter()

@router.post("/login")
async def login_for_admin(payload: AdminLoginRequest):
    try:
        admin = await get_user_by_email(payload.email)
        if not admin or not verify_password(payload.password, admin["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        token = create_access_token(subject=str(admin["_id"]))
        return {"message": "Admin Logged In Successfully", "token": token} 
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while logging in admin: {str(e)}"
        )