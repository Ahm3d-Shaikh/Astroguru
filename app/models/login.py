from pydantic import BaseModel


class LoginRequest(BaseModel):
    phone: str
    country_code: str
    otp: str


class AdminLoginRequest(BaseModel):
    email: str
    password: str