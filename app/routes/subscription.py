from fastapi import APIRouter, HTTPException, status, Depends, Request
from app.models.subscription import SubscriptionRequest, PlanRequest, PlanUpdateRequest
from app.deps.auth_deps import get_current_user
from app.services.subscription_service import save_subscription, fetch_subscription, add_plan_to_db, fetch_plans, update_plan_by_id, verify_storekit2_transaction, verify_apple_notification, handle_apple_event
from app.utils.admin import is_user_admin
import httpx
import os
import json
from bson import json_util


router = APIRouter()

@router.post("/plan")
async def add_subscription_plan(payload: PlanRequest, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        await add_plan_to_db(payload)
        return {"message": "Subscription Plan Added Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding subscription plan: {str(e)}"
        )
    

@router.get("/plan")
async def fetch_subscription_plan(current_user = Depends(get_current_user)):
    try:
        plans = await fetch_plans()
        result_json = json.loads(json_util.dumps(plans))
        return {"message": "Plans Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding subscription plan: {str(e)}"
        )
    

@router.patch("/plan/{id}")
async def update_plan(id: str, plan_update: PlanUpdateRequest, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        update_data = plan_update.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
        updated_plan = await update_plan_by_id(update_data, id)
        return {"message": "Prediction Updated Successfully", "result": updated_plan}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating plan: {str(e)}"
        )

@router.post("/")
async def add_subscription(payload: SubscriptionRequest, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        # 1. Verify Apple StoreKit 2 transaction
        apple_data = await verify_storekit2_transaction(
            payload.signed_transaction_info
        )

        # 2. Persist subscription and grant credits
        await save_subscription(user_id, apple_data)
        return {"message": "Subscription Added Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while verifying receipt: {str(e)}"
        )

@router.post("/apple/notifications")
async def apple_notifications(request: Request):
    body = await request.json()
    signed_payload = body.get("signedPayload")

    if not signed_payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing signedPayload")

    notification = await verify_apple_notification(signed_payload)

    await handle_apple_event(notification)
    return {"status": "ok"}

@router.get("/")
async def get_subscription_status(current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        subscription = await fetch_subscription(user_id)
        return {"message": "Subscription Fetched Successfully", "result": subscription}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching subscription status: {str(e)}"
        )