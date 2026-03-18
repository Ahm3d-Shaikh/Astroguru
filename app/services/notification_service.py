from app.db.mongo import db
from bson import ObjectId
from datetime import datetime
from fastapi import HTTPException, status
from app.utils.mongo import convert_mongo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.clients.firebase import send_push_notification
import random


async def create_notification(user_id: str, title: str, message: str, type: str = "general"):
    notif = {
        "user_id": ObjectId(user_id),
        "title": title,
        "message": message,
        "status": "pending",
        "send_at": datetime.utcnow(),
        "type": type,
        "is_read": False,
        "sent_at": None,
        "created_at": datetime.utcnow()
    }
    result = await db.notifications.insert_one(notif)
    notif["_id"] = result.inserted_id
    return notif


async def create_global_notification(title: str, message: str):

    users = db.users.find({"role": "user", "is_enabled": True, "is_onboarded": True}, {"_id": 1})

    notifications = []

    async for user in users:
        notifications.append({
            "user_id": user["_id"],
            "title": title,
            "message": message,
            "type": "general",
            "status": "pending",
            "send_at": datetime.utcnow(),
            "is_read": False,
            "created_at": datetime.utcnow()
        })

    if notifications:
        await db.notifications.insert_many(notifications)


scheduler = AsyncIOScheduler()

async def push_pending_notifications():
    pending = db.notifications.find({"status": "pending", "send_at": {"$lte": datetime.utcnow()}})
    async for notif in pending:
        devices = db.user_devices.find({"user_id": notif["user_id"]})
        async for device in devices:
            try:
                await send_push_notification(device["device_token"], notif["title"], notif["message"])
                await db.notifications.update_one(
                    {"_id": notif["_id"]},
                    {"$set": {"status": "sent", "sent_at": datetime.utcnow()}}
                )
            except Exception:
                await db.notifications.update_one(
                    {"_id": notif["_id"]},
                    {"$set": {"status": "failed"}}
                )


async def daily_morning_notification():
    await create_global_notification(
        "Good morning 🌞",
        "Today's energy is shifting. Stay open to new opportunities."
    )


async def night_reflection_notification():
    await create_global_notification(
        "Night reflection 🌙",
        "Take a moment to reflect. Tomorrow brings a new cosmic shift."
    )

MYSTERY_MESSAGES = [
    "Something is shifting in your 7th house tonight.",
    "We see you overthinking again. Just send the text.",
    "The universe is testing your patience today.",
]

async def mystery_notification():
    message = random.choice(MYSTERY_MESSAGES)

    await create_global_notification(
        "A message for you ✨",
        message
    )

def start_scheduler():

    if not scheduler.running:

        scheduler.add_job(
            push_pending_notifications,
            "interval",
            minutes=1,
            id="push_notifications",
            replace_existing=True
        )

        scheduler.add_job(
            daily_morning_notification,
            "cron",
            hour=8,
            minute=0,
            id="daily_morning",
            replace_existing=True
        )

        scheduler.add_job(
            night_reflection_notification,
            "cron",
            hour=22,
            minute=0,
            id="night_reflection",
            replace_existing=True
        )

        scheduler.add_job(
            mystery_notification,
            "cron",
            hour=15,
            minute=0,
            id="mystery",
            replace_existing=True
        )

        scheduler.start()

async def fetch_notifications(user_id):
    try:
        cursor = db.notifications.find({"user_id": ObjectId(user_id)})
        notifications = await cursor.to_list(length=None)
        if not notifications:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notifications Not Found")
        return convert_mongo(notifications)
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching notifications from db: {str(e)}"
        )
    

async def mark_notification_as_read(id, user_id):
    try:
        await db.notifications.update_one(
            {"_id": ObjectId(id), "user_id": ObjectId(user_id)},
            {
                "$set": {
                    "is_read": True
                }
            }
        )
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating notification in db: {str(e)}"
        )
    

async def fetch_notifications_for_admin():
    try:
        pipeline = [
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id",
                    "foreignField": "_id",
                    "as": "user"
                }
            },
            {
                "$unwind": {
                    "path": "$user",
                    "preserveNullAndEmptyArrays": True
                }
            },
            {
                "$addFields": {
                    "user_name": "$user.name"
                }
            },
            {
                "$project": {
                    "user": 0 
                }
            }
        ]

        cursor = db.notifications.aggregate(pipeline)
        notifications = await cursor.to_list(length=None)

        if not notifications:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notifications Not Found"
            )

        return convert_mongo(notifications)

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching notifications for dashboard: {str(e)}"
        )
    

async def register_user_device_in_db(payload, user_id):
    try:
        existing = await db.user_devices.find_one({
        "device_token": payload.device_token
    })

        if existing:
            await db.user_devices.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "user_id": ObjectId(user_id),
                        "platform": payload.platform,
                        "is_active": True,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return {"message": "Device updated"}

        await db.user_devices.insert_one({
            "user_id": ObjectId(user_id),
            "device_token": payload.device_token,
            "platform": payload.platform,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

    except HTTPException as http_err:
        raise http_err
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while registering device in db: {str(e)}"
        )