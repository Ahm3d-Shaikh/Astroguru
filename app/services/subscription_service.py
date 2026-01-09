from fastapi import HTTPException, status
from app.db.mongo import db
from datetime import datetime
from bson import ObjectId


async def save_subscription(user_id, payload, apple_response):
    try:
        in_app = apple_response["receipt"].get("in_app", [])
        if not in_app:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No in-app purchase found in receipt"
            )

        # Get latest transaction
        latest_txn = max(
            in_app,
            key=lambda x: int(x["purchase_date_ms"])
        )

        transaction_id = latest_txn["transaction_id"]

        # Prevent duplicate transactions
        existing = await db.user_subscriptions.find_one({
            "transaction_id": transaction_id
        })
        if existing:
            return  # already processed
        
        await db.user_subscriptions.insert_one({
            "user_id": user_id,
            "product_id": latest_txn["product_id"],
            "transaction_id": transaction_id,
            "original_transaction_id": latest_txn.get("original_transaction_id"),
            "receipt_data": payload.receipt_data,
            "purchase_date": datetime.utcfromtimestamp(
                int(latest_txn["purchase_date_ms"]) / 1000
            ),
            "expiry_date": (
                datetime.utcfromtimestamp(int(latest_txn["expires_date_ms"]) / 1000)
                if latest_txn.get("expires_date_ms") else None
            ),
            "status": "active",
            "sandbox": payload.is_sandbox,
            "platform": "iOS"
        })
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while saving subscription to db: {str(e)}"
        )
    

async def fetch_subscription(user_id):
    try:
        subscription = await db.user_subscriptions.find_one({"user_id": ObjectId(user_id)})
        if not subscription:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subcription Not Found")
        
        return subscription
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise