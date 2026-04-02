from app.db.mongo import db
from bson import ObjectId
from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.utils.mongo import convert_mongo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.clients.firebase import send_push_notification
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import random
import asyncio


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


async def create_notification_for_users_at_local_hour(title: str, message: str, target_hour: int, type: str):
    now_utc = datetime.now(timezone.utc)
 
    users = db.users.find(
        {"role": "user", "is_enabled": True, "is_onboarded": True},
        {"_id": 1, "timezone": 1}
    )
 
    notifications = []
    async for user in users:
        tz_str = user.get("timezone", "Asia/Kolkata")
        if not tz_str:
            continue
 
        try:
            user_tz = ZoneInfo(tz_str)
        except ZoneInfoNotFoundError:
            continue
 
        local_time = now_utc.astimezone(user_tz)

        if local_time.hour != target_hour or local_time.minute >= 10:
            continue

        start_of_day_local = local_time.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_day_utc = start_of_day_local.astimezone(timezone.utc)
        
        already_sent = await db.notifications.find_one({
            "user_id": user["_id"],
            "type": type,  
            "created_at": {"$gte": start_of_day_utc}
        })

        if already_sent:
            continue
 
        notifications.append({
            "user_id": user["_id"],
            "title": title,
            "message": message,
            "type": type,
            "status": "pending",
            "send_at": now_utc,
            "is_read": False,
            "created_at": now_utc
        })
 
    if notifications:
        await db.notifications.insert_many(notifications)

scheduler = AsyncIOScheduler()

async def push_test_notification_to_device(payload, user_id):
    cursor = db.user_devices.find({
        "user_id": ObjectId(user_id),
        "is_active": True
    })
    devices = await cursor.to_list(length=None)
    for device in devices:
        try:
            result = await send_push_notification(
                device["device_token"],
                "Test",
                payload.notification
            )
        except Exception:
            raise Exception

async def push_pending_notifications():
    print("Running push_pending_notifications")
    pending = db.notifications.find({
        "status": "pending",
        "send_at": {"$lte": datetime.now(timezone.utc)}
    })

    async for notif in pending:
        user = await db.users.find_one({
            "_id": notif["user_id"],
            "is_push_notifications_enabled": True
        })

        if not user:
            continue  

        devices = db.user_devices.find({
            "user_id": notif["user_id"],
            "is_active": True
        })

        success = False

        async for device in devices:
            try:
                await send_push_notification(
                    device["device_token"],
                    notif["title"],
                    notif["message"]
                )
                success = True
            except Exception:
                continue

        if success:
            await db.notifications.update_one(
                {"_id": notif["_id"]},
                {"$set": {"status": "sent", "sent_at": datetime.now(timezone.utc)}}
            )
        else:
            await db.notifications.update_one(
                {"_id": notif["_id"]},
                {"$set": {"status": "failed"}}
            )


async def notification_cycle():
    print("Running notification cycle")

    await create_notification_for_users_at_local_hour(
        "Good morning 🌞",
        "Today's energy is shifting. Stay open to new opportunities.",
        8,
        "morning"
    )

    await create_notification_for_users_at_local_hour(
        "Night reflection 🌙",
        "Take a moment to reflect. Tomorrow brings a new cosmic shift.",
        22,
        "night"
    )

    message = random.choice(MYSTERY_MESSAGES)

    await create_notification_for_users_at_local_hour(
        "A message for you ✨",
        message,
        15,
        "mystery"
    )

MYSTERY_MESSAGES = [
    "Something is shifting in your 7th house tonight 🌌✨.",
    "We see you overthinking again 🤔💌. Just send the text 📲.",
    "The universe is testing your patience today ⏳🌠.",
    "Your Moon in Scorpio is feeling the intensity today 🌙🦂. Here is how to protect your energy 🛡️💖.",
    "The universe has your back today 🌌💫. Repeat after us: I am open to new opportunities 🌱🌞.",
    "The New Moon in Pisces is here 🌑♓—the perfect time to set intentions for the month ahead ✨📝.",
    "Mercury is officially retrograde 🔄☿. Double-check those emails 📧 and leave early for your meetings 🏃‍♂️💨!",
    "Venus enters Leo today ♀️🦁. Expect a spark in your social life ✨💃🕺.",
    "The Moon is Void-of-Course until 4 PM 🌙🚫. Avoid making big decisions or signing contracts until then 📝❌.",
    "We see you overthinking again 🤔✨. The stars say: just send the text 📲💌.",
    "The stars missed you ✨💫. Since you've been gone, Saturn has moved 🪐—here's how it affects you now 🔮.",
    "Something major is happening in your 7th House tonight 🌌🏠. Curious? 👀✨"
]

def start_scheduler():

    if not scheduler.running:

        scheduler.add_job(
            notification_cycle,
            "interval",
            minutes=5, 
            id="notification_cycle",
            replace_existing=True
        )

        scheduler.add_job(
            push_pending_notifications,
            "interval",
            minutes=1,
            id="push_notifications",
            replace_existing=True,
            max_instances=3  
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
    

async def mark_all_notifications_as_read(user_id):
    try:
        await db.notifications.update_many(
            {"user_id": ObjectId(user_id)},
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
            detail=f"Error while marking all notifications as read: {str(e)}"
        )

async def mark_all_notifications_as_read_on_dashboard():
    try:
        await db.notifications.update_many(
            {},
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
            detail=f"Error while marking all notifications as read: {str(e)}"
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
    

async def fetch_dashboard_notifications():
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
            detail=f"Error while fetching dashboard notifications from db: {str(e)}"
        )
    
async def push_notifications_to_users_helper(payload, is_subscribed: bool):
    try:
        base_match = {
            "role": "user",
            "is_enabled": True,
            "is_push_notifications_enabled": True
        }

        pipeline = [
            {"$match": base_match}
        ]

        # ✅ Apply subscription filter using $lookup
        if is_subscribed:
            pipeline.extend([
                {
                    "$lookup": {
                        "from": "user_subscriptions",
                        "localField": "_id",
                        "foreignField": "user_id",
                        "as": "subscription"
                    }
                },
                {
                    "$match": {
                        "subscription.0": {"$exists": True}
                    }
                }
            ])

        cursor = db.users.aggregate(pipeline)

        async for user in cursor:
            devices_cursor = db.user_devices.find({
                "user_id": user["_id"],
                "is_active": True
            })

            tokens = [
                device["device_token"]
                async for device in devices_cursor
                if device.get("device_token")
            ]

            if not tokens:
                continue

            # 🚀 Send in parallel per user
            tasks = [
                send_push_notification(token, payload.title, payload.message)
                for token in tokens
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if isinstance(res, Exception):
                    print(f"Push failed: {res}")

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while pushing notifications: {str(e)}"
        )