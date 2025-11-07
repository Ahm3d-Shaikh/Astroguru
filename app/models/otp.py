from pydantic import BaseModel


class OtpRequest(BaseModel):
    phone: str
