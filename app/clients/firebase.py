import firebase_admin
from firebase_admin import messaging, credentials
from dotenv import load_dotenv
import asyncio
import os

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
firbase_path = os.path.join(BASE_DIR, "app", "config", "firebase_key.json")
cred = credentials.Certificate(firbase_path)
firebase_admin.initialize_app(cred)

async def send_push_notification(device_token: str, title: str, body: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        lambda: messaging.send(
            messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=device_token,
    )
        )
    )