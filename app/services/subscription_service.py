from fastapi import HTTPException, status
from app.db.mongo import db
from datetime import datetime, timedelta
from typing import Optional, Dict
from bson import ObjectId
from jose import jwt
import requests
from datetime import datetime, timezone
from app.utils.mongo import convert_mongo
import os 

APPLE_KEYS_URL = "https://api.storekit.itunes.apple.com/in-app-purchase/publicKeys"
APPLE_BUNDLE_ID = os.getenv("APPLE_BUNDLE_ID")

_cached_keys = None

def get_apple_public_keys():
    global _cached_keys
    if not _cached_keys:
        _cached_keys = requests.get(APPLE_KEYS_URL).json()["keys"]
    return _cached_keys



def ms_to_datetime(ms: int | None):
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)

async def verify_storekit2_transaction(signed_transaction_info: str):
    keys = get_apple_public_keys()

    header = jwt.get_unverified_header(signed_transaction_info)
    kid = header["kid"]

    key = next((k for k in keys if k["kid"] == kid), None)
    if not key:
        raise HTTPException(400, "Invalid Apple key")

    payload = jwt.decode(
        signed_transaction_info,
        key,
        algorithms=["ES256"],
        audience="appstoreconnect-v1",
        options={"verify_exp": True}
    )

    if payload["bundleId"] != APPLE_BUNDLE_ID:
        raise HTTPException(400, "Invalid bundle ID")

    return {
        "transaction_id": payload["transactionId"],
        "product_id": payload["productId"],
        "purchase_date": datetime.fromtimestamp(
            payload["purchaseDate"] / 1000
        ),
        "expires_at": (
            datetime.fromtimestamp(payload["expiresDate"] / 1000)
            if payload.get("expiresDate")
            else None
        )
    }


async def add_user_credits(user_id: str, credits: int, reason: str, purchase_value: Optional[Dict[str, any]] = None):
    if credits <= 0:
        raise ValueError("Credits must be positive")
    

    update_ops = {
        "$inc": {"credits_balance": credits},
        "$set": {
            "reason": reason,
            "updated_at": datetime.utcnow()
        }
    }

    purchase_str = None
    if purchase_value:
        update_ops["$inc"]["total_spent"] = purchase_value["amount"]
        purchase_str = f"{purchase_value['amount']} {purchase_value['currency']}"

    await db.user_wallet.update_one(
        {"user_id": ObjectId(user_id)},
        update_ops,
        upsert=True
    )

    await log_user_transaction(
        user_id=user_id,
        reason=reason,
        credits_change=credits,
        purchase_value=purchase_str
    )


async def deduct_user_credits(user_id: str, credits: int, reason: str, purchase_value: Optional[str] = None):
    if credits <= 0:
        raise ValueError("Credits to deduct must be positive")

    result = await db.user_wallet.find_one_and_update(
        {
            "user_id": ObjectId(user_id),
            "credits_balance": {"$gte": credits}
        },
        {
            "$inc": {"credits_balance": -credits}
        },
        return_document=True
    )

    if not result:
        raise HTTPException(
            status_code=400,
            detail="Insufficient credits"
        )
    
    await log_user_transaction(
        user_id=user_id,
        reason=reason,
        credits_change=-credits,
        purchase_value=purchase_value
    )

    return result["credits_balance"]

async def save_subscription(user_id: str, data: dict):
    try:
        existing = await db.user_subscriptions.find_one({
            "apple_transaction_id": data["transactionId"]
        })
        if existing:
            return

        plan = await db.subscription_plans.find_one({
            "apple_product_id": data["productId"]
        })
        if not plan:
            raise HTTPException(400, "Invalid Apple product")
        

        purchase_date = ms_to_datetime(data.get("originalTransactionDateIOS"))
        expires_at = ms_to_datetime(data.get("expirationDateIOS"))

        await db.user_subscriptions.insert_one({
            "user_id": ObjectId(user_id),
            "plan_id": plan["_id"],
            "apple_product_id": plan["apple_product_id"],
            "apple_transaction_id": data.get("transactionId"),
            "credits_granted": plan["credits"],
            "purchase_date": purchase_date,
            "expires_at": expires_at,
            "status": "active",
            "platform": data.get("platform"),
            "environment": data.get("environment")
        })

        reason = f"{plan['credits']} Coin Purchase"
        amount = plan["price"]          # e.g. 9.99
        currency = plan["currency"]
        purchase_value = {"amount": amount, "currency": currency}
        await add_user_credits(user_id, plan["credits"], reason, purchase_value)
        coins = await fetch_user_coins(user_id)
        return coins
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while saving subscription: {str(e)}"
        )    

async def fetch_subscription(user_id):
    try:
        pipeline = [
            {
                "$match": {
                    "user_id": ObjectId(user_id)
                }
            },
            {
                "$lookup": {
                    "from": "subscription_plans",
                    "localField": "plan_id",
                    "foreignField": "_id",
                    "as": "plan_details"
                }
            },
            {
                "$unwind": {
                    "path": "$plan_details",
                    "preserveNullAndEmptyArrays": True
                }
            }
        ]

        cursor = db.user_subscriptions.aggregate(pipeline)
        result = await cursor.to_list(length=1)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription Not Found"
            )

        doc = convert_mongo(result)
        return doc[0]

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching subscription: {str(e)}"
        )

async def add_plan_to_db(payload):
    try:    
        await db.subscription_plans.insert_one({
            "name": payload.name,
            "apple_product_id": payload.apple_product_id,
            "credits": payload.credits,
            "price": payload.price,
            "currency": payload.currency,
            "type": payload.type,
            "duration_days": payload.duration_days 
        })
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding subscription plan: {str(e)}"
        )


async def fetch_plans():
    try:
        cursor = db.subscription_plans.find()
        plans = await cursor.to_list(length=None)

        if not plans:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Plans Found")
        return plans
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching subscription plans: {str(e)}"
        )
    

async def update_plan_by_id(update_data, id):
    try:
        object_id = ObjectId(id)
        result = await db.subscription_plans.update_one({"_id": object_id}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

        updated_plan = await db.subscription_plans.find_one({"_id": object_id})
        updated_plan["_id"] = str(updated_plan["_id"])
        return updated_plan
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating plan: {str(e)}"
        )



async def verify_apple_notification(signed_payload: str):
    keys = await get_apple_public_keys()

    header = jwt.get_unverified_header(signed_payload)
    kid = header["kid"]

    key = next((k for k in keys if k["kid"] == kid), None)
    if not key:
        raise HTTPException(400, "Invalid Apple key")

    payload = jwt.decode(
        signed_payload,
        key,
        algorithms=["ES256"],
        audience="appstoreconnect-v1",
        options={"verify_exp": True}
    )

    return payload

async def get_user_id_from_tx(transaction_id):
    subscription = await db.user_subscriptions.find_one({"apple_transaction_id": ObjectId(transaction_id)})
    return subscription["user_id"]


async def log_user_transaction(
    user_id: str,
    reason: str,
    credits_change: int,
    purchase_value: Optional[str] = None
):
    await db.user_transactions.insert_one({
        "user_id": ObjectId(user_id),
        "reason": reason,
        "credits_change": credits_change,
        "purchase": purchase_value,
        "created_at": datetime.utcnow()
    })


async def handle_apple_event(event: dict):
    notification_type = event.get("notificationType")
    data = event.get("data", {})

    tx = data.get("transaction", {})  

    transaction_id = tx.get("transactionId")
    product_id = tx.get("productId")

    if not transaction_id or not product_id:
        return  

    plan = await db.subscription_plans.find_one({
        "apple_product_id": product_id
    })
    if not plan:
        return

    user_id = await get_user_id_from_tx(transaction_id)
    if not user_id:
        return

    purchase_date = ms_to_datetime(tx.get("originalTransactionDateIOS"))
    expires_at = ms_to_datetime(tx.get("expirationDateIOS"))

    if notification_type in ["SUBSCRIBED", "DID_RENEW"]:
        existing = await db.user_subscriptions.find_one({
            "apple_transaction_id": transaction_id
        })

        if not existing:
            await db.user_subscriptions.insert_one({
                "user_id": ObjectId(user_id),
                "plan_id": plan["_id"],
                "apple_product_id": product_id,
                "apple_transaction_id": transaction_id,
                "credits_granted": plan["credits"],
                "purchase_date": purchase_date,
                "expires_at": expires_at,
                "status": "active",
                "platform": "ios",
                "environment": tx.get("environmentIOS")
            })

            reason = f"{plan['credits']} Coin Purchase"
            purchase_value = f"{plan['price']} {plan['currency']}"

            await add_user_credits(
                user_id=user_id,
                credits=plan["credits"],
                reason=reason,
                purchase_value=purchase_value
            )

    elif notification_type in ["CANCEL", "EXPIRED"]:
        await db.user_subscriptions.update_one(
            {"apple_transaction_id": transaction_id},
            {"$set": {"status": "inactive"}}
        )

    elif notification_type == "REFUND":
        await db.user_subscriptions.update_one(
            {"apple_transaction_id": transaction_id},
            {"$set": {"status": "refunded"}}
        )

        reason = f"Refund – {plan['credits']} Coins"
        purchase_value = f"{plan['price']} {plan['currency']}"

        await deduct_user_credits(
            user_id=user_id,
            credits=plan["credits"],
            reason=reason,
            purchase_value=purchase_value
        )




async def fetch_transaction_history(user_id):
    try:
        cursor = db.user_transactions.find({"user_id": ObjectId(user_id)}).sort("created_at", -1)
        history = await cursor.to_list(length=None)

        if not history:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Transaction History Found")
        return history
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching transaction history: {str(e)}"
        )
    

async def assign_coins_to_user(id, payload):
    try:
        await db.user_wallet.update_one(
        {"user_id": ObjectId(id)},
        {
            "$inc": {"credits_balance": payload.coins},
            "$set": {
                "reason": payload.reason,
                "updated_at": datetime.utcnow()
            }
        },
        upsert=True
    )
        reason = "Admin-added Reward"
        await log_user_transaction(id, reason, payload.coins)
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while assigning coins to user: {str(e)}"
        )
    

async def fetch_user_coins(user_id):
    try:
        coins = await db.user_wallet.find_one({"user_id": ObjectId(user_id)})
        if not coins:
            return 0
        
        coins["_id"] = str(coins["_id"])
        coins["user_id"] = str(coins["user_id"])
        return coins["credits_balance"]
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching coins: {str(e)}"
        )
    


async def fetch_user_transactions():
    try:
        cursor = db.user_wallet.find()
        transactions = await cursor.to_list(length=None)
        return transactions
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user transactions: {str(e)}"
        )