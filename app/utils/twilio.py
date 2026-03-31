from app.clients.twilio_client import twilio_client, TWILIO_PHONE_NUMBER, TWILIO_SERVICE_SID
from fastapi import HTTPException, status
import asyncio
from functools import partial


async def send_otp_sms(country_code: str, phone: str):
    try:
        phone_e164 = f"{country_code}{phone}"
        verification = twilio_client.verify \
            .v2 \
            .services(TWILIO_SERVICE_SID) \
            .verifications \
            .create(to=phone_e164, channel='sms')
        return verification.sid
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while sending OTP via Verify API: {str(e)}"
        )
    

async def verify_otp(country_code: str, phone: str, code: str):
    phone_e164 = f"{country_code}{phone}"
    loop = asyncio.get_running_loop()
    func = partial(
        twilio_client.verify.v2.services(TWILIO_SERVICE_SID)
        .verification_checks.create,
        to=phone_e164,
        code=code
    )
    return await loop.run_in_executor(None, func)