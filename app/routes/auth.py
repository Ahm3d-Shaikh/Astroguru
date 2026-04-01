from fastapi import APIRouter, HTTPException, status, Depends
from app.models.user import UserCreate
from app.models.login import LoginRequest
from app.deps.auth_deps import get_current_user
from app.models.otp import OtpRequest
from app.utils.twilio import send_otp_sms, verify_otp
from app.services.auth_service import create_access_token, generate_otp, get_user_by_phone
from app.utils.helper import get_zodiac_sign
from app.services.subscription_service import fetch_user_coins, add_user_credits
from datetime import datetime, timedelta
from app.db.mongo import db
from bson import ObjectId
import pytz


router = APIRouter()

@router.post("/onboard")
async def onboard_user(payload: UserCreate, current_user = Depends(get_current_user)):
    try:
        user_id = ObjectId(current_user["_id"])        
        user_doc_raw = payload.dict()

        dob_date = user_doc_raw["date_of_birth"]          
        tob_time = user_doc_raw["time_of_birth"]  
        tz_name = user_doc_raw["timezone"]
        

        dob_str = dob_date.isoformat()                    
        tob_str = tob_time.strftime("%H:%M")              

        birth_timestamp = datetime(
            year=dob_date.year,
            month=dob_date.month,
            day=dob_date.day,
            hour=tob_time.hour,
            minute=tob_time.minute,
        )

        tz = pytz.timezone(tz_name)
        birth_localized = tz.localize(birth_timestamp)

        utc_offset = birth_localized.utcoffset().total_seconds() / 3600

        user_doc = {
            "name": user_doc_raw["name"],
            "gender": user_doc_raw["gender"],
            "date_of_birth": dob_str,            
            "time_of_birth": tob_str,    
            "birth_timestamp": birth_timestamp,
            "place_of_birth": user_doc_raw["place_of_birth"],
            "lat": user_doc_raw["lat"],
            "long": user_doc_raw["long"], 
            "timezone": tz_name,
            "utc_offset": utc_offset,
            "is_onboarded": True, 
            "is_push_notifications_enabled": True,
            "created_at": datetime.utcnow(),     
        }

        res = await db.users.update_one(
            {"_id": user_id},
            {"$set": user_doc}
        )

        if res.modified_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")

        reason = "Onboarding bonus"
        await add_user_credits(user_id, 50, reason)
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
        user = await get_user_by_phone(payload.phone, payload.country_code)
        if user:
            if not user.get("is_enabled", True):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account Disabled. Please contact admin."
                )
            user_id = user["_id"]
        else:
            res = await db.users.insert_one({
                "phone": payload.phone,
                "country_code": payload.country_code,
                "created_at": datetime.utcnow(),
                "is_onboarded": False,
                "is_enabled": True,
                "role": payload.role
            })
            user_id = res.inserted_id

        verification_sid = await send_otp_sms(payload.country_code, payload.phone)        
        await db.otp_table.update_one(
            {"user_id": user_id},
            {"$set": {
                "created_at": datetime.utcnow(),
                "verification_sid": verification_sid,
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
    

@router.post("/verify-otp")
async def verify_otp_controller(payload: LoginRequest):
    try:
        user = await get_user_by_phone(payload.phone, payload.country_code)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found. Please Request OTP Again")
        
        if not user["is_enabled"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account Disabled")
        otp = await db.otp_table.find_one({"user_id": user["_id"]})
        if not otp or "verification_sid" not in otp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP")
               
        verification_check = await verify_otp(payload.country_code, payload.phone, payload.otp)
        if verification_check.status != "approved":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP")
        
        return {"message": "OTP Verified Successfully"}
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
        user = await get_user_by_phone(payload.phone, payload.country_code)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found. Please Request OTP Again")
        
        if not user["is_enabled"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account Disabled")
        otp = await db.otp_table.find_one({"user_id": user["_id"]})
        if not otp or "verification_sid" not in otp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP")
               
        verification_check = await verify_otp(payload.country_code, payload.phone, payload.otp)
        if verification_check.status != "approved":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP")
        
        await db.otp_table.delete_one({"user_id": user["_id"]})
        token = create_access_token(subject=str(user["_id"]))
        coins = await fetch_user_coins(user["_id"])
        user_dict = dict(user)
        user_dict["_id"] = str(user["_id"])
        user_dict["zodiac_sign"] = get_zodiac_sign(user_dict.get("date_of_birth"))
        return {"message": "User Logged In Successfully", "token": token, "user": user_dict, "coins": coins}
    
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )