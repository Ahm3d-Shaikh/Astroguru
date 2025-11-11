from pydantic import BaseModel
from typing import Optional

class PredictionCreate(BaseModel):
    name: str
    type: str
    prompt: str


class PredictionUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    prompt: Optional[str] = None
