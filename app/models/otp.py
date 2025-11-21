from pydantic import BaseModel


class OtpRequest(BaseModel):
    country_code: str
    phone: str
