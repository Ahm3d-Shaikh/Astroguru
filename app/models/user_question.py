from pydantic import BaseModel

class UserQuestionObj(BaseModel):
    user_question: str