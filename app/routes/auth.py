from fastapi import APIRouter, HTTPException, status, Depends
from app.models.user import UserCreate
from app.models.login import LoginRequest
from app.deps.auth_deps import get_current_user
from app.models.otp import OtpRequest
from app.utils.twilio import send_otp_sms
from app.services.auth_service import create_access_token, generate_otp, get_user_by_phone
from datetime import datetime, timedelta
from app.db.mongo import db
from bson import ObjectId


router = APIRouter()

@router.post("/onboard")
async def onboard_user(payload: UserCreate, current_user = Depends(get_current_user)):
    try:
        user_id = ObjectId(current_user["_id"])        
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
            "gender": user_doc_raw["gender"],
            "date_of_birth": dob_str,            
            "time_of_birth": tob_str,            
            "birth_timestamp": birth_timestamp,
            "lat": user_doc_raw["lat"],
            "long": user_doc_raw["long"], 
            "is_onboarded": True, 
            "created_at": datetime.utcnow(),     
        }

        res = await db.users.update_one(
            {"_id": user_id},
            {"$set": user_doc}
        )

        if res.modified_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")

        return {"message": "User Onboarded Successfully"}
    
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
        user = await get_user_by_phone(payload.phone)
        if not user:
            res = await db.users.insert_one({
                "phone": payload.phone,
                "created_at": datetime.utcnow(),
                "is_onboarded": False
            })
            user_id = res.inserted_id
        else:
            user_id = user["_id"]
        
        # otp = generate_otp()
        otp = "123456"
        # await send_otp_sms(payload.phone, otp)
        
        await db.otp_table.update_one(
            {"user_id": user_id},
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
        user = await get_user_by_phone(payload.phone)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found. Please Request OTP Again")
        
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