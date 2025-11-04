from pydantic import BaseModel


class LoginRequest(BaseModel):
    phone: str
    otp: str
