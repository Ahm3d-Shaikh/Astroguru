from app.clients.twilio_client import twilio_client, TWILIO_PHONE_NUMBER
from fastapi import HTTPException, status

async def send_otp_sms(phone: str, otp: str):
    try:
        message = twilio_client.messages.create(
            body=f"Use the following OTP to complete your login: {otp}. It will expire in 10 minutes.",
            from_= TWILIO_PHONE_NUMBER,
            to= phone
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while sending otp via SMS: {str(e)}"
        )