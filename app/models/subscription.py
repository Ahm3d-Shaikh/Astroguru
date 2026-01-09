from pydantic import BaseModel

class ReceiptRequest(BaseModel):
    receipt_data: str
    is_sandbox: bool = False
    user_id: str