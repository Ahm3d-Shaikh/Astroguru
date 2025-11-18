from pydantic import BaseModel, constr, field_validator
from typing import Annotated, Optional
from datetime import time, date


class UserProfileCreate(BaseModel):
    name: Annotated[str, constr(strip_whitespace=True, min_length=1)]
    gender: Annotated[str, constr(strip_whitespace=True, min_length=1)]
    date_of_birth: date
    time_of_birth: time
    lat: Annotated[str, constr(strip_whitespace=True, min_length=1)]
    long: Annotated[str, constr(strip_whitespace=True, min_length=1)]

    @field_validator("lat", "long")
    def lat_long_must_be_nonempty(cls, v, info):
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        try:
            val = float(v)
        except ValueError:
            raise ValueError(f"{info.field_name} must be a valid number")
        return v
    

class UserProfileUpdate(BaseModel):
    name : Optional[str] = None
    gender : Optional[str] = None
    date_of_birth: Optional[date] = None
    time_of_birth: Optional[time] = None
    lat: Optional[str] = None
    long: Optional[str] = None