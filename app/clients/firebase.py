import firebase_admin
from firebase_admin import messaging, credentials
import asyncio
import os
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
firebase_path = os.path.join(BASE_DIR, "app", "config", "firebase_key.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_path)
    firebase_admin.initialize_app(cred)


def _send_fcm_message(device_token: str, title: str, body: str, data: Optional[dict] = None):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=device_token,
        data=data or {}
    )

    return messaging.send(message)


async def send_push_notification(device_token: str, title: str, body: str, data: Optional[dict] = None):
    try:
        loop = asyncio.get_running_loop()

        response = await loop.run_in_executor(
            None,
            _send_fcm_message,
            device_token,
            title,
            body,
            data
        )

        return {
            "success": True,
            "message_id": response
        }

    except messaging.UnregisteredError:
        return {
            "success": False,
            "error": "UNREGISTERED_TOKEN",
            "delete_token": True
        }

    except messaging.InvalidArgumentError as e:
        return {
            "success": False,
            "error": f"INVALID_ARGUMENT: {str(e)}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"FCM_ERROR: {str(e)}"
        }