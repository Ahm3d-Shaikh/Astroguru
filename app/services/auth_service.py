from passlib.context import CryptContext
import bcrypt
import hashlib
from jose import jwt, JWTError
import os
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId
from app.clients.firebase import verify_social_token
import random



JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGO = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 


def generate_otp() -> str:
    return f"{random.randint(100000, 999999)}"

def _pw_to_digest(password: str) -> bytes:
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    digest = _pw_to_digest(password)  
    salt = bcrypt.gensalt()           
    hashed = bcrypt.hashpw(digest, salt)
    return hashed.decode("utf-8")     



def verify_password(plain_password: str, stored_hash: str) -> bool:
    digest = _pw_to_digest(plain_password)
    return bcrypt.checkpw(digest, stored_hash.encode("utf-8"))

def create_access_token(subject: str, expires_delta: timedelta = None):
    now = datetime.utcnow()
    exp = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": str(subject),
        "iat": now.timestamp(),
        "exp": exp.timestamp(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def get_user_by_email(email: str):
    try:
        return await db.users.find_one({"email": email})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user by email: {str(e)}"
        )
    

async def get_user_by_phone(phone: str, country_code: str):
    try:
        return await db.users.find_one({"phone": phone, "country_code": country_code})
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user by phone: {str(e)}"
        )

async def get_user_by_id(user_id: str):
    try:
        return await db.users.find_one({"_id": ObjectId(user_id)})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user by id: {str(e)}"
        )


async def social_login_service(id_token: str, provider: str):
    """
    Verify a Firebase social token (Google / Apple) and find-or-create the user.

    Lookup order:
      1. Existing user with matching social_id  → login directly
      2. Existing user with matching email       → link social_id, then login
      3. No match anywhere                       → create new user

    Returns: (jwt_token, user_dict, is_new_user)
    """
    # ── 1. Verify token with Firebase (blocking call → executor) ──────────────
    decoded = await verify_social_token(id_token)

    firebase_uid = decoded.get("uid")
    email        = decoded.get("email")
    name         = decoded.get("name") or ""
    avatar       = decoded.get("picture") or ""

    if not firebase_uid:
        raise HTTPException(status_code=401, detail="Invalid token: missing uid")

    # ── 2. Find by social_id ────────────────────────────────────────────────────
    user = await db.users.find_one({"social_id": firebase_uid})
    is_new_user = False

    # ── 3. Try to link with an existing phone-login account (same email) ───────
    if not user and email:
        user = await db.users.find_one({"email": email})
        if user:
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {
                    "social_id": firebase_uid,
                    "auth_provider": provider,
                    "avatar": avatar,
                }}
            )
            user = await db.users.find_one({"_id": user["_id"]})

    # ── 4. Brand-new user ───────────────────────────────────────────────────────
    if not user:
        is_new_user = True
        res = await db.users.insert_one({
            "email":        email,
            "name":         name,
            "avatar":       avatar,
            "social_id":    firebase_uid,
            "auth_provider": provider,
            "is_onboarded": False,
            "is_enabled":   True,
            "role":         "user",
            "created_at":   datetime.utcnow(),
        })
        user = await db.users.find_one({"_id": res.inserted_id})

    # ── 5. Block check ──────────────────────────────────────────────────────────
    if not user.get("is_enabled", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account Disabled. Please contact admin."
        )

    token = create_access_token(subject=str(user["_id"]))
    user["_id"] = str(user["_id"])
    return token, user, is_new_user
