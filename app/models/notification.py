from pydantic import BaseModel
from typing import Optional
from bson import ObjectId

class NotificationCreate(BaseModel):
    user_id: str
    title: str
    message: str
    status: str
    is_read: bool
    type: str

class NotificationOut(NotificationCreate):
    id: str
    status: str
    sent_at: Optional[str]
    created_at: str


class RegisterDevicePayload(BaseModel):
    device_token: str
    platform: str


class TestNotification(BaseModel):
    notification: str