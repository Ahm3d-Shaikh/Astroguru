from pydantic import BaseModel


class OtpRequest(BaseModel):
    email: str
