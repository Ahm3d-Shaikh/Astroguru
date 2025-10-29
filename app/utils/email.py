from app.clients.email import fm, MessageSchema, MessageType
from typing import List
from fastapi import HTTPException, status

async def send_otp_email(recipient: str, otp: str):
    try:
        message = MessageSchema(
            subject="Login Verification Code",
            recipients=[recipient],
            body=f"Use the following OTP to complete your login: {otp}. It will expire in 10 mins.",
            subtype=MessageType.html
        )

        await fm.send_message(message)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending otp email: {str(e)}"
        )