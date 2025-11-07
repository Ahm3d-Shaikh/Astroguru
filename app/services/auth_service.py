from passlib.context import CryptContext
import bcrypt
import hashlib
from jose import jwt, JWTError
import os
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId
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
    

async def get_user_by_phone(phone: str):
    try:
        return await db.users.find_one({"phone": phone})
    except HTTPException:
        raise
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
