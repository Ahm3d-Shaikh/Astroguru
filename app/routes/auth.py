from fastapi import APIRouter, HTTPException, status
from app.models.user import UserCreate
from app.models.login import LoginRequest
from app.services.auth_service import get_user_by_email, hash_password, create_access_token, verify_password
from bson import ObjectId
from datetime import datetime
from app.db.mongo import db


router = APIRouter()

@router.post("/signup")
async def register_user(payload: UserCreate):
    try:
        existing = await get_user_by_email(payload.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="User Already Registered"
            )
        
        user_doc_raw = payload.dict()

        raw_password = user_doc_raw.pop("password")
        password_hash = hash_password(raw_password)


        dob_date = user_doc_raw["date_of_birth"]          
        tob_time = user_doc_raw["time_of_birth"]          

        dob_str = dob_date.isoformat()                    
        tob_str = tob_time.strftime("%H:%M")              

        birth_timestamp = datetime(
            year=dob_date.year,
            month=dob_date.month,
            day=dob_date.day,
            hour=tob_time.hour,
            minute=tob_time.minute,
        )

        user_doc = {
            "name": user_doc_raw["name"],
            "email": user_doc_raw["email"],
            "gender": user_doc_raw["gender"],
            "date_of_birth": dob_str,            
            "time_of_birth": tob_str,            
            "birth_timestamp": birth_timestamp,  
            "place_of_birth": user_doc_raw["place_of_birth"],
            "password_hash": password_hash,
            "created_at": datetime.utcnow(),     
        }

        res = await db.users.insert_one(user_doc)

        user_id = str(res.inserted_id)
        token = create_access_token(subject=user_id)
        return {"message": "User Registered Successfully", "access_token": token, "user_id": user_id}
    
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )

@router.post("/login")
async def login(payload: LoginRequest):
    try:
        user = await get_user_by_email(payload.email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
        
        if not verify_password(payload.password, user.get("password_hash", "")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
        token = create_access_token(subject=str(user["_id"]))
        return {"message": "User Logged In Successfully", "access_token": token}
    
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )