from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    otp: str


class AdminLoginRequest(BaseModel):
    email: str
    password: str