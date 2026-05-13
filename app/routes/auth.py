from fastapi import APIRouter, HTTPException, status, Depends
from app.models.user import UserCreate, SocialLoginRequest
from app.models.login import LoginRequest
from app.deps.auth_deps import get_current_user
from app.models.otp import OtpRequest
from app.utils.twilio import send_otp_sms, verify_otp
from app.services.auth_service import create_access_token, generate_otp, get_user_by_phone, social_login_service
from app.utils.helper import get_zodiac_sign
from app.services.subscription_service import fetch_user_coins, add_user_credits
from datetime import datetime, timedelta
from app.db.mongo import db
from bson import ObjectId
import pytz
import os


router = APIRouter()

TESTING_NUMBER = os.getenv("TESTING_NUMBER")
TESTING_OTP = os.getenv("TESTING_OTP")

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

        # ── Social-login users: phone is required during onboarding ───────────
        is_social_user = not current_user.get("phone")
        if is_social_user:
            phone        = payload.phone
            country_code = payload.country_code
            if not phone or not country_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number and country code are required"
                )

            # Check if phone already belongs to another account
            existing_phone_user = await db.users.find_one({
                "phone": phone,
                "country_code": country_code,
                "_id": {"$ne": user_id}
            })

            if existing_phone_user:
                existing_id = existing_phone_user["_id"]
                existing_auth = existing_phone_user.get("auth_provider")

                if existing_auth in ("google", "apple") or existing_phone_user.get("social_id"):
                    # Two different social accounts claiming the same phone → block
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This phone number is already linked to another social account"
                    )
                else:
                    # Phone belongs to an existing OTP account → link social identity to it
                    # and delete the duplicate social-only account
                    social_fields = {
                        "social_id":    current_user.get("social_id"),
                        "auth_provider": current_user.get("auth_provider"),
                        "avatar":       current_user.get("avatar"),
                        "email":        current_user.get("email"),
                    }
                    await db.users.update_one(
                        {"_id": existing_id},
                        {"$set": {k: v for k, v in social_fields.items() if v}}
                    )
                    # Remove the duplicate social-only account
                    await db.users.delete_one({"_id": user_id})
                    # Issue a fresh token for the merged (original phone) account
                    from app.services.auth_service import create_access_token
                    new_token = create_access_token(subject=str(existing_id))
                    await add_user_credits(existing_id, 50, "Onboarding bonus")
                    return {
                        "message": "Account linked to existing phone account",
                        "token": new_token,
                        "merged": True,
                    }

            user_doc["phone"]        = phone
            user_doc["country_code"] = country_code

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
    
@router.post("/request-otp/phone")
async def request_otp_for_phone(payload: OtpRequest):
    try:
        verification_sid = await send_otp_sms(payload.country_code, payload.phone)        
        return {"message": "OTP Sent Successfully"}
    
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
        is_testing = payload.phone == TESTING_NUMBER
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

        verification_sid = "testing" if is_testing else await send_otp_sms(payload.country_code, payload.phone)        
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
        
        is_testing = payload.phone == TESTING_NUMBER
        if is_testing:
            if payload.otp != TESTING_OTP:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid OTP"
                )
        else:
            otp = await db.otp_table.find_one({"user_id": user["_id"]})
            if not otp or "verification_sid" not in otp:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP")
                
            verification_check = await verify_otp(payload.country_code, payload.phone, payload.otp)
            if verification_check.status != "approved":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP")
            
        await db.otp_table.delete_one({"user_id": user["_id"]})
        if is_testing:
            await db.user_wallet.update_one(
                {"user_id": ObjectId(user["_id"])},
                {
                    "$inc": {"credits_balance": 10000},
                    "$set": {
                        "reason": "Test Account",
                        "updated_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
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


@router.post("/social-login")
async def social_login(payload: SocialLoginRequest):
    """
    Authenticate with a Firebase ID token issued by Google or Apple Sign-In.
    - Verifies the token with Firebase Admin SDK.
    - Finds or creates the user in MongoDB.
    - Returns our own JWT (same format as phone login).
    - is_new_user = true  → mobile should navigate to onboarding screen.
    - is_new_user = false → mobile should navigate to home screen.
    """
    try:
        token, user, is_new_user = await social_login_service(payload.id_token, payload.provider)
        coins = await fetch_user_coins(user["_id"])
        user["zodiac_sign"] = get_zodiac_sign(user.get("date_of_birth"))
        return {
            "message": "Logged In Successfully",
            "token": token,
            "user": user,
            "coins": coins,
            "is_new_user": is_new_user,
        }
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Social login failed: {str(e)}"
        )