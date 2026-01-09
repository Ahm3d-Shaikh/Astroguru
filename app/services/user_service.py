from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId
from datetime import datetime
from app.utils.helper import get_or_fetch_astrology_data, fetch_user_details, get_zodiac_sign, build_indu_lagna_chart
from app.services.conversation_service import fetch_conversations
from app.services.report_service import fetch_user_reports
from app.utils.mongo import convert_mongo
from app.clients.gemini_client import client
from google.genai import types
import asyncio



async def fetch_users(type_filter: str = None):
    try:
        query = {}
        if type_filter:
            query["role"] = type_filter
        cursor = db.users.find(query)
        users = await cursor.to_list(length=None)

        if not users:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Users Found")
        
        return users
    except HTTPException as http_err:
        raise http_err
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
    

async def fetch_dashboard_details_for_user(id):
    try:
        user_details = await fetch_user_details(id)
        astrology_data_task = get_or_fetch_astrology_data(id, id, user_details)
        conversations_task = fetch_conversations(id, None)
        user_reports_task = fetch_user_reports(id, None)

        astrology_data, conversations_raw, user_reports_raw = await asyncio.gather(
            astrology_data_task,
            conversations_task,
            user_reports_task,
            return_exceptions=True

        )

        indu_lagna = astrology_data.get("indu_lagna")
        d1_chart = astrology_data.get("horoscope_charts").get("d1")
        indu_lagna_chart = build_indu_lagna_chart(indu_lagna, d1_chart)
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
            "conversations": conversations,
            "reports": user_reports,
            "indu_lagna_chart": indu_lagna_chart
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