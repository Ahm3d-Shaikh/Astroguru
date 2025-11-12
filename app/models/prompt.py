from pydantic import BaseModel
from typing import Optional


class PromptCreate(BaseModel):
    category: str
    prompt: str


class PromptUpdate(BaseModel):
    category: Optional[str] = None
    prompt: Optional[str] = None