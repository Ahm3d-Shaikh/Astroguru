from fastapi import APIRouter, HTTPException, status, Depends
from app.models.subscription import ReceiptRequest
from app.deps.auth_deps import get_current_user
from app.services.subscription_service import save_subscription
import httpx
import os


router = APIRouter()
APPLE_PROD = os.getenv("APPLE_PROD")
APPLE_SANDBOX = os.getenv("APPLE_SANDBOX")

@router.post("/verify-receipt")
async def verify_receipt(payload: ReceiptRequest, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        url = APPLE_SANDBOX if payload.is_sandbox else APPLE_PROD
        async with httpx.AsyncClient() as client:
            response = await client.post(
                APPLE_PROD,
                json={"receipt-data": payload.receipt_data}
            )
        result = response.json()

        # Handle sandbox receipt sent to prod
        if result.get("status") == 21007:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    APPLE_SANDBOX,
                    json={"receipt-data": payload.receipt_data}
                )
            result = response.json()

        if result.get("status") != 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Receipt")
        
        receipt_info = result.get("receipt")
        await save_subscription(user_id, payload, result)
        return {"message": "Receipt Verified Successfully", "result": receipt_info}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while verifying receipt: {str(e)}"
        )