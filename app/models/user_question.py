from pydantic import BaseModel
from typing import Optional
from app.utils.enums.category import Category

class UserQuestionObj(BaseModel):
    user_question: str
    conversation_id: Optional[str] = None


class ChatQuestionPayload(BaseModel):
    user_question: str