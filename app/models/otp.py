from pydantic import BaseModel
from typing import Optional


class OtpRequest(BaseModel):
    country_code: str
    phone: str
    role: Optional[str] = "user"

