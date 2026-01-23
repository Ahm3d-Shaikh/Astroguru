from pydantic import BaseModel
from enum import Enum
from typing import Optional
from datetime import datetime


class SubscriptionRequest(BaseModel):
    signed_transaction_info: str

class PlanType(str, Enum):
    subscription = "subscription"
    consumable = "consumable"

class PlanRequest(BaseModel):
    name: str
    apple_product_id: str
    credits: int
    price: float
    currency: Optional[str] = "USD"
    type: PlanType
    duration_days: Optional[int] = None

class PlanUpdateRequest(BaseModel):
    name: Optional[str] = None
    apple_product_id: Optional[str] = None
    credits: Optional[int] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    type: Optional[PlanType] = None
    duration_days: Optional[int] = None 


class UserTransaction(BaseModel):
    user_id: str
    transaction_id: str
    product_id: str
    plan_id: str
    credits_change: int
    type: str  
    source: str  
    status: str  
    created_at: datetime = datetime.utcnow()
    expires_at: Optional[datetime] = None