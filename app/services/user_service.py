from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId
from datetime import datetime, timezone
from app.utils.helper import get_or_fetch_astrology_data, fetch_user_details, get_zodiac_sign, build_indu_lagna_chart, build_karakamsha_chart, build_arudha_lagna_chart, fetch_profile_details
from app.services.conversation_service import fetch_conversations
from app.services.report_service import fetch_user_reports, fetch_user_reports_for_admin, fetch_user_compatibility_reports_for_admin
from app.services.astrology_service import fetch_user_profile_summary
from app.services.subscription_service import fetch_user_coins
from app.utils.helper import convert_to_local_timezone
from app.utils.mongo import convert_mongo
from app.clients.gemini_client import client
from google.genai import types
import asyncio
import re
import pytz



async def fetch_users(type_filter: str = None):
    try:
        pipeline = []

        if type_filter:
            pipeline.append({
                "$match": {"role": type_filter}
            })

        pipeline.append({
            "$lookup": {
                "from": "user_profiles",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "sub_users"
            }
        })

        pipeline.append({
            "$lookup": {
                "from": "user_subscriptions",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "subscriptions"
            }
        })

        pipeline.append({
            "$addFields": {
                "is_subscribed": {
                    "$gt": [{"$size": "$subscriptions"}, 0]
                }
            }
        })

        pipeline.append({
            "$project": {
                "subscriptions": 0
            }
        })

        users = await db.users.aggregate(pipeline).to_list(length=None)

        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No Users Found"
            )

        return users

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching users: {str(e)}"
        )    

async def fetch_user_by_id(id):
    try:
        user = await db.users.find_one({"_id": ObjectId(id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
        
        user["_id"] = str(user["_id"])
        return user
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user by id: {str(e)}"
        )
    

async def fetch_logged_in_user_details(user_id):
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
        
        user["_id"] = str(user["_id"])
        user["zodiac_sign"] = get_zodiac_sign(user.get("date_of_birth"))
        cursor = db.user_devices.find({"user_id": ObjectId(user_id)})
        devices = await cursor.to_list(length=None)
        user["user_devices"] = convert_mongo(devices)
        return user
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching logged in user details: {str(e)}"
        )
    
def parse_mongo_datetime(data):
    """
    Recursively parse ISO datetime strings to datetime objects.
    """
    if isinstance(data, dict):
        return {k: parse_mongo_datetime(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [parse_mongo_datetime(i) for i in data]
    else:
        # try parsing datetime
        if isinstance(data, str):
            try:
                dt = datetime.fromisoformat(data)
                # assume UTC if naive
                if dt.tzinfo is None:
                    dt = pytz.UTC.localize(dt)
                return dt
            except ValueError:
                return data
        else:
            return data

async def fetch_dashboard_details_for_user(id, profile_id: str | None = None, search_term: str | None = None):
    try:
        if profile_id == id:
            profile_details = await fetch_user_details(id)
        else:
            profile_details = await fetch_profile_details(id, profile_id)
        astrology_data_task = get_or_fetch_astrology_data(id, profile_id, profile_details)
        conversations_task = fetch_conversations(id, profile_id, search_term)
        user_reports_task = fetch_user_reports_for_admin(id, profile_id)
        user_compatibility_reports_task = fetch_user_compatibility_reports_for_admin(id, profile_id)

        astrology_data, conversations_raw, user_reports_raw, user_compatibility_reports_raw = await asyncio.gather(
            astrology_data_task,
            conversations_task,
            user_reports_task,
            user_compatibility_reports_task,
            return_exceptions=True

        )
        profile_summary = await fetch_user_profile_summary(profile_details, conversations_raw, user_reports_raw)
        indu_lagna = astrology_data.get("indu_lagna")
        karakamsha_lagna = astrology_data.get("karakamsha_lagna")
        arudha_lagna = astrology_data.get("arudha_lagna")
        d1_chart = astrology_data.get("horoscope_charts").get("d1")
        indu_lagna_chart = build_indu_lagna_chart(indu_lagna, d1_chart)
        karakamsha_lagna_chart = build_karakamsha_chart(karakamsha_lagna, d1_chart)
        arudha_lagna_chart = build_arudha_lagna_chart(arudha_lagna, d1_chart)
        planet_positions = astrology_data.get("planet_positions")
        FIELDS_TO_ROUND = {"fullDegree", "normDegree", "speed"}

        for planet, data in planet_positions.items():
            for field in FIELDS_TO_ROUND:
                if field in data and isinstance(data[field], (int, float)):
                    data[field] = round(data[field], 2)
        if isinstance(conversations_raw, Exception):
            conversations = []
        else:
            conversations = convert_mongo(conversations_raw)

        if isinstance(user_reports_raw, Exception):
            user_reports = []
        else:
            user_reports = convert_mongo(user_reports_raw)

        if isinstance(user_compatibility_reports_raw, Exception):
            user_compatibility_reports = []
        else:
            user_compatibility_reports = convert_mongo(user_compatibility_reports_raw)

        timezone = profile_details.get("timezone", "Asia/Kolkata")
        conversations = parse_mongo_datetime(conversations)
        conversations = convert_to_local_timezone(conversations, timezone)
        return {
            "charts": astrology_data.get("horoscope_charts"),
            "planet_positions": planet_positions,
            "conversations": conversations,
            "reports": user_reports,
            "compatibility_reports": user_compatibility_reports,
            "indu_lagna_chart": indu_lagna_chart,
            "karakamsha_lagna_chart": karakamsha_lagna_chart,
            "arudha_lagna_chart": arudha_lagna_chart,
            "profile_summary": profile_summary
        }
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching dashboard details from db: {str(e)}"
        )

async def fetch_user_stats(id):
    try:
        simple_reports = await db.user_reports.count_documents({
            "user_id": ObjectId(id),
            "$or": [
                {"file_url": {"$ne": None}},
                {"report_text": {"$ne": None}}
            ]
        })
        compatibility_reports = await db.user_compatibility_reports.count_documents({"user_id": ObjectId(id)})
        coins = await fetch_user_coins(id)
        total_revenue_pipeline = [
            {
                "$match": {
                    "user_id": ObjectId(id)  
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_revenue": {"$sum": "$total_spent"}
                }
            }
        ]

        result = await db.user_wallet.aggregate(total_revenue_pipeline).to_list(length=1)
        total_revenue = result[0]["total_revenue"] if result else 0
        return {
            "total_spent": round(total_revenue),
            "coins": coins,
            "reports_generated": simple_reports + compatibility_reports
        }
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user stats from db: {str(e)}"
        )

async def delete_user_by_id(id):
    try:
        await db.users.delete_one({"_id": ObjectId(id)})
        await db.conversations.delete_many({"user_id": ObjectId(id)})
        await db.chat_history.delete_many({"user_id": ObjectId(id)})
        await db.astrological_information.delete_many({"user_id": ObjectId(id)})
        await db.user_profiles.delete_many({"user_id": ObjectId(id)})
        await db.user_reports.delete_many({"user_id": ObjectId(id)})
        await db.user_compatibility_reports.delete_many({"user_id": ObjectId(id)})
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting user: {str(e)}"
        )


async def delete_logged_in_user_by_id(id: str):
    try:
        result = await db.users.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"is_enabled": False}}
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting user: {str(e)}"
        )


async def edit_user_details(user_id, update_data):
    try:
        object_id = ObjectId(user_id)
        update_fields = {}

        dob = update_data.get("date_of_birth")   
        tob = update_data.get("time_of_birth")   

        if dob:
            update_fields["date_of_birth"] = dob.isoformat()

        if tob:
            update_fields["time_of_birth"] = tob.strftime("%H:%M")

        if dob and tob:
            birth_timestamp = datetime(
                year=dob.year,
                month=dob.month,
                day=dob.day,
                hour=tob.hour,
                minute=tob.minute,
            )
            update_fields["birth_timestamp"] = birth_timestamp

        for field in ["country_code","phone", "name", "gender", "lat", "long", "place_of_birth", "is_push_notifications_enabled"]:
            if field in update_data and update_data[field] is not None:
                update_fields[field] = update_data[field]

            
        result = await db.users.update_one({"_id": object_id}, {"$set": update_fields})
        if result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        updated_user = await db.users.find_one({"_id": object_id})
        updated_user["_id"] = str(updated_user["_id"])
        return updated_user
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while editing logged in user: {str(e)}"
        )
    


async def fetch_users_summary():
    try:
        now = datetime.now(timezone.utc)
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if current_month_start.month == 1:
            prev_month_start = current_month_start.replace(year=current_month_start.year - 1, month=12)
        else:
            prev_month_start = current_month_start.replace(month=current_month_start.month - 1)
        prev_month_end = current_month_start

        def calculate_percentage_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return ((current - previous) / previous) * 100

        # Single aggregation replaces 12 sequential count_documents calls.
        # Groups each onboarded user into total / current-month / prev-month buckets by gender.
        user_pipeline = [
            {"$match": {"role": "user", "is_onboarded": True}},
            {
                "$addFields": {
                    "gender_lower": {"$toLower": "$gender"},
                    "in_current_month": {"$gte": ["$created_at", current_month_start]},
                    "in_prev_month": {
                        "$and": [
                            {"$gte": ["$created_at", prev_month_start]},
                            {"$lt": ["$created_at", prev_month_end]},
                        ]
                    },
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "males": {"$sum": {"$cond": [{"$eq": ["$gender_lower", "male"]}, 1, 0]}},
                    "females": {"$sum": {"$cond": [{"$eq": ["$gender_lower", "female"]}, 1, 0]}},
                    "other": {"$sum": {"$cond": [{"$eq": ["$gender_lower", "other"]}, 1, 0]}},
                    "current_month": {"$sum": {"$cond": ["$in_current_month", 1, 0]}},
                    "prev_month": {"$sum": {"$cond": ["$in_prev_month", 1, 0]}},
                    "current_month_males": {
                        "$sum": {"$cond": [{"$and": ["$in_current_month", {"$eq": ["$gender_lower", "male"]}]}, 1, 0]}
                    },
                    "prev_month_males": {
                        "$sum": {"$cond": [{"$and": ["$in_prev_month", {"$eq": ["$gender_lower", "male"]}]}, 1, 0]}
                    },
                    "current_month_females": {
                        "$sum": {"$cond": [{"$and": ["$in_current_month", {"$eq": ["$gender_lower", "female"]}]}, 1, 0]}
                    },
                    "prev_month_females": {
                        "$sum": {"$cond": [{"$and": ["$in_prev_month", {"$eq": ["$gender_lower", "female"]}]}, 1, 0]}
                    },
                    "current_month_other": {
                        "$sum": {"$cond": [{"$and": ["$in_current_month", {"$eq": ["$gender_lower", "other"]}]}, 1, 0]}
                    },
                    "prev_month_other": {
                        "$sum": {"$cond": [{"$and": ["$in_prev_month", {"$eq": ["$gender_lower", "other"]}]}, 1, 0]}
                    },
                }
            },
        ]

        # Single aggregation for all revenue figures.
        revenue_pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_revenue": {"$sum": "$total_spent"},
                    "current_month_revenue": {
                        "$sum": {
                            "$cond": [{"$gte": ["$updated_at", current_month_start]}, "$total_spent", 0]
                        }
                    },
                    "prev_month_revenue": {
                        "$sum": {
                            "$cond": [
                                {"$and": [
                                    {"$gte": ["$updated_at", prev_month_start]},
                                    {"$lt": ["$updated_at", prev_month_end]},
                                ]},
                                "$total_spent",
                                0,
                            ]
                        }
                    },
                }
            }
        ]

        user_result, revenue_result = await asyncio.gather(
            db.users.aggregate(user_pipeline).to_list(length=1),
            db.user_wallet.aggregate(revenue_pipeline).to_list(length=1),
        )

        u = user_result[0] if user_result else {}
        r = revenue_result[0] if revenue_result else {}

        return {
            "users": u.get("total", 0),
            "users_trend": round(calculate_percentage_change(u.get("current_month", 0), u.get("prev_month", 0)), 2),
            "males": u.get("males", 0),
            "male_trend": round(calculate_percentage_change(u.get("current_month_males", 0), u.get("prev_month_males", 0)), 2),
            "females": u.get("females", 0),
            "female_trend": round(calculate_percentage_change(u.get("current_month_females", 0), u.get("prev_month_females", 0)), 2),
            "other": u.get("other", 0),
            "other_trend": round(calculate_percentage_change(u.get("current_month_other", 0), u.get("prev_month_other", 0)), 2),
            "revenue": round(r.get("total_revenue", 0)),
            "revenue_trend": round(calculate_percentage_change(r.get("current_month_revenue", 0), r.get("prev_month_revenue", 0)), 2),
        }
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user summary from db: {str(e)}"
        )
    

async def fetch_user_onboarding_status(payload):
    try:
        user = await db.users.find_one({"phone": payload.phone, "country_code": payload.country_code, "is_enabled": True})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No User Found")
        
        return user["is_onboarded"]
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching onboarding status: {str(e)}"
        )
    

async def block_user_from_db(id):
    try:
        result = await db.users.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"is_enabled": False}}
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while blocking user from db: {str(e)}"
        )
    

async def unblock_user_from_db(id):
    try:
        result = await db.users.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"is_enabled": True}}
        )

        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while unblocking user from db: {str(e)}"
        )
    

async def duplicate_phone_helper(payload):
    try:
        user = await db.users.find_one({"country_code": payload.country_code, "phone": payload.phone})
        if user:
            return True
        return False
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while checking duplicate phone in db: {str(e)}"
        )