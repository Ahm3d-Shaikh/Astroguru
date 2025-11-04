from pydantic import BaseModel
from typing import Optional
from app.utils.enums.category import Category

class UserQuestionObj(BaseModel):
    user_question: str
