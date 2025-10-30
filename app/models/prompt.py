from pydantic import BaseModel


class PromptCreate(BaseModel):
    category: str
    prompt: str