from pydantic import BaseModel


class LoginRequest(BaseModel):
    phone: str
    otp: str


class AdminLoginRequest(BaseModel):
    email: str
    password: str