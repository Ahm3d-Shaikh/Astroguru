from fastapi import APIRouter, HTTPException, status
from app.models.user import UserCreate
from app.models.login import LoginRequest
from app.models.otp import OtpRequest
from app.utils.email import send_otp_email
from app.services.auth_service import get_user_by_email, create_access_token, generate_otp
from datetime import datetime, timedelta
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
            "lat": user_doc_raw["lat"],
            "long": user_doc_raw["long"],  
            "created_at": datetime.utcnow(),     
        }

        res = await db.users.insert_one(user_doc)

        user_id = str(res.inserted_id)
        token = create_access_token(subject=user_id)
        return {"message": "User Registered Successfully"}
    
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )
    

@router.post("/request-otp")
async def request_otp(payload: OtpRequest):
    try:
        user = await get_user_by_email(payload.email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
        
        otp = generate_otp()
        await send_otp_email(payload.email, otp)
        
        await db.otp_table.update_one(
            {"user_id": user["_id"]},
            {"$set": {
                "otp": otp,
                "created_at": datetime.utcnow(),
            }},
            upsert=True
        )
        return {"message": "OTP Sent Successfully"}
    
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
        
        otp = await db.otp_table.find_one({"user_id": user["_id"], "otp": payload.otp})
        if not otp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP")
        
        created_at = otp["created_at"]
        if not created_at or datetime.utcnow() > created_at + timedelta(minutes=10):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OTP Expired")
        
        await db.otp_table.delete_one({"user_id": user["_id"]})
        token = create_access_token(subject=str(user["_id"]))
        user_dict = dict(user)
        user_dict["_id"] = str(user["_id"])
        return {"message": "User Logged In Successfully", "token": token, "user": user_dict}
    
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )