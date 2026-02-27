from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId
from datetime import datetime, timezone
from app.utils.helper import get_or_fetch_astrology_data, fetch_user_details, get_zodiac_sign, build_indu_lagna_chart, build_karakamsha_chart, build_arudha_lagna_chart, fetch_profile_details
from app.services.conversation_service import fetch_conversations
from app.services.report_service import fetch_user_reports, fetch_user_reports_for_admin
from app.services.astrology_service import fetch_user_profile_summary
from app.utils.mongo import convert_mongo
from app.clients.gemini_client import client
from google.genai import types
import asyncio
import re



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
        return user
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching logged in user details: {str(e)}"
        )
    

async def fetch_dashboard_details_for_user(id, profile_id: str | None = None, search_term: str | None = None):
    try:
        if profile_id == id:
            profile_details = await fetch_user_details(id)
        else:
            profile_details = await fetch_profile_details(id, profile_id)
        astrology_data_task = get_or_fetch_astrology_data(id, profile_id, profile_details)
        conversations_task = fetch_conversations(id, profile_id, search_term)
        user_reports_task = fetch_user_reports_for_admin(id, profile_id)

        astrology_data, conversations_raw, user_reports_raw = await asyncio.gather(
            astrology_data_task,
            conversations_task,
            user_reports_task,
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
        return {
            "charts": astrology_data.get("horoscope_charts"),
            "planet_positions": planet_positions,
            "conversations": conversations,
            "reports": user_reports,
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

        for field in ["country_code","phone", "name", "gender", "lat", "long", "place_of_birth"]:
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

        current_month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        if current_month_start.month == 1:
            prev_month_start = current_month_start.replace(
                year=current_month_start.year - 1, month=12
            )
        else:
            prev_month_start = current_month_start.replace(
                month=current_month_start.month - 1
            )

        prev_month_end = current_month_start
        users_count = await db.users.count_documents({"role": "user", "is_onboarded": True})
        male_users_count = await db.users.count_documents({
            "role": "user",
            "is_onboarded": True,
            "gender": re.compile("^male$", re.IGNORECASE) 
        })

        female_users_count = await db.users.count_documents({
            "role": "user",
            "is_onboarded": True,
            "gender": re.compile("^female$", re.IGNORECASE)
        })

        def build_gender_filter(gender):
            return {
                "role": "user",
                "is_onboarded": True,
                "gender": re.compile(f"^{gender}$", re.IGNORECASE)
            }

        current_month_users = await db.users.count_documents({
            "role": "user",
            "is_onboarded": True,
            "created_at": {"$gte": current_month_start}
        })

        previous_month_users = await db.users.count_documents({
            "role": "user",
            "is_onboarded": True,
            "created_at": {
                "$gte": prev_month_start,
                "$lt": prev_month_end
            }
        })

        current_month_males = await db.users.count_documents({
            **build_gender_filter("male"),
            "created_at": {"$gte": current_month_start}
        })
        previous_month_males = await db.users.count_documents({
            **build_gender_filter("male"),
            "created_at": {"$gte": prev_month_start, "$lt": prev_month_end}
        })

        current_month_females = await db.users.count_documents({
            **build_gender_filter("female"),
            "created_at": {"$gte": current_month_start}
        })
        previous_month_females = await db.users.count_documents({
            **build_gender_filter("female"),
            "created_at": {"$gte": prev_month_start, "$lt": prev_month_end}
        })


        total_revenue_pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_revenue": {"$sum": "$total_spent"}  
                }
            }
        ]

        result = await db.user_wallet.aggregate(total_revenue_pipeline).to_list(length=1)
        total_revenue = result[0]["total_revenue"] if result else 0


        async def get_revenue_between(start, end=None):
            match_stage = {
                "updated_at": {"$gte": start}
            }
            if end:
                match_stage["updated_at"]["$lt"] = end

            pipeline = [
                {"$match": match_stage},
                {
                    "$group": {
                        "_id": None,
                        "total": {"$sum": "$total_spent"}
                    }
                }
            ]

            result = await db.user_wallet.aggregate(
                pipeline
            ).to_list(length=1)

            return result[0]["total"] if result else 0

        current_month_revenue = await get_revenue_between(current_month_start)
        previous_month_revenue = await get_revenue_between(
            prev_month_start,
            prev_month_end
        )

        def calculate_percentage_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return ((current - previous) / previous) * 100

        user_trend = calculate_percentage_change(
            current_month_users,
            previous_month_users
        )

        revenue_trend = calculate_percentage_change(
            current_month_revenue,
            previous_month_revenue
        )

        male_trend = calculate_percentage_change(current_month_males, previous_month_males)
        female_trend = calculate_percentage_change(current_month_females, previous_month_females)

        return {
            "users": users_count,
            "users_trend": round(user_trend, 2),
            "males": male_users_count,
            "male_trend": round(male_trend, 2),
            "females": female_users_count,
            "female_trend": round(female_trend, 2),
            "revenue": round(total_revenue),
            "revenue_trend": round(revenue_trend, 2)
        }
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user summary from db: {str(e)}"
        )