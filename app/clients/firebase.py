import firebase_admin
from firebase_admin import messaging, credentials
from dotenv import load_dotenv
import asyncio
import os

load_dotenv()

# service_key = os.getenv("FIREBASE_KEY")
# cred = credentials.Certificate(service_key)
# firebase_admin.initialize_app(cred)

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