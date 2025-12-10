from pydantic import BaseModel
from typing import Optional, List

class CompatibilityCreate(BaseModel):
    type: str
    prompt: str


class CompatibilityUpdate(BaseModel):
    type: Optional[str] = None
    prompt: Optional[str] = None


class CompatibilityReportCreate(BaseModel):
    profile_id: List[str]
    type: str