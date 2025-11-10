from pydantic import BaseModel
from typing import Optional

class ReportCreate(BaseModel):
    name: str
    type: str
    sub_title: str
    description: str
    prompt: str


class ReportUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    sub_title: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
