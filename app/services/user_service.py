from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId
from datetime import datetime
from app.utils.helper import get_or_fetch_astrology_data, fetch_user_details
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
        astrology_data = await get_or_fetch_astrology_data(id, id, user_details)
        astrology_summary = "\n".join(f"{key}: {value}" for key, value in astrology_data.items())

        system_prompt = f"""
        You are a Vedic Astrologer. You will be given the user details and astrology details for the user. 
        You must describe each chart. The charts are:

        {["d1","d2","d3","d4","d5","d6","d7","d8","d9","d10","d11","d12","d16","d20","d24","d27","d30","d40","d45","d60"]}

        Note:
        - ALWAYS respond in third person. For example: "This person's Rashi Chart (D1) reflects the overall personality."
        """


        contents = [
            f"User Details:\n{user_details}",
            f"Astrology Data:\n{astrology_summary}"
        ]
        
        config = types.GenerateContentConfig(
        temperature = 0.2,
        max_output_tokens = 10000,
        system_instruction = system_prompt
        )

        gemini_task = client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=config,
        )
        conversations_task = fetch_conversations(id, None)
        user_reports_task = fetch_user_reports(id, None)

        gemini_response, conversations_raw, user_reports_raw = await asyncio.gather(
            gemini_task,
            conversations_task,
            user_reports_task
        )
        charts = gemini_response.text
        conversations = convert_mongo(conversations_raw)
        user_reports = convert_mongo(user_reports_raw)
        
        return {
            "charts": charts,
            "conversations": conversations,
            "reports": user_reports
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