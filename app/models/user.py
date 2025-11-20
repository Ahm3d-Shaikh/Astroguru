from typing import Annotated, Optional
from pydantic import BaseModel, EmailStr, constr, field_validator
from datetime import time, date


class UserCreate(BaseModel):
    name: Annotated[str, constr(strip_whitespace=True, min_length=1)]
    gender: Annotated[str, constr(strip_whitespace=True, min_length=1)]
    role: Optional[str] = "user"
    date_of_birth: date
    time_of_birth: time
    lat: Annotated[str, constr(strip_whitespace=True, min_length=1)]
    long: Annotated[str, constr(strip_whitespace=True, min_length=1)]
    place_of_birth: Annotated[str, constr(strip_whitespace=True, min_length=1)]

    @field_validator("lat", "long")
    def lat_long_must_be_nonempty(cls, v, info):
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        try:
            val = float(v)
        except ValueError:
            raise ValueError(f"{info.field_name} must be a valid number")
        return v

class UserInDB(BaseModel):
    id: str
    name: str
    country_code:str
    phone: str
    gender: str
    date_of_birth: date
    time_of_birth: time
    lat: str
    long: str
    place_of_birth: str


class Admin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    phone: Optional[str] = None
    name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    time_of_birth: Optional[time] = None
    lat: Optional[str] = None
    long: Optional[str] = None