from pydantic import BaseModel
from typing import Optional


class ConversationUpdate(BaseModel):
    title: Optional[str] = None