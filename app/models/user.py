from pydantic import BaseModel, EmailStr
from datetime import time, date


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    gender: str
    date_of_birth: date
    time_of_birth: time
    lat: str
    long: str

class UserInDB(BaseModel):
    id: str
    name: str
    email: EmailStr
    gender: str
    date_of_birth: date
    time_of_birth: time
    lat: str
    long: str