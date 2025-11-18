from fastapi import HTTPException, status
from app.db.mongo import db
from app.clients.openai_client import openai_client
import os
import httpx
from base64 import b64encode
from datetime import datetime
from bson import ObjectId
from app.services.prompt_service import fetch_categories
import asyncio


ASTRO_API_USER_ID = os.getenv("ASTROLOGY_API_USER_ID")
ASTRO_API_KEY = os.getenv("ASTROLOGY_API_KEY")

BASE_URL = "https://json.astrologyapi.com/v1"


async def save_astrology_data(user_id: str, astrology_data: dict):
    try:
        record = {
            "user_id": user_id,
            "astro_data": astrology_data.get("astro_details", {}),
            "planets_data": astrology_data.get("planet_positions", {}),
            "dashas_data": astrology_data.get("dashas", {}),
            "updated_at": datetime.utcnow().isoformat()
        }

        await db.astrological_information.update_one(
            {"user_id": user_id},
            {"$set": record},
            upsert=True
        )
        return True
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving astrology data: {str(e)}"
        )


async def fetch_kundli(user_details: dict):
    auth_header = b64encode(f"{ASTRO_API_USER_ID}:{ASTRO_API_KEY}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/json"
    }

    payload = {
        "day": int(user_details["date_of_birth"].split("-")[2]),
        "month": int(user_details["date_of_birth"].split("-")[1]),
        "year": int(user_details["date_of_birth"].split("-")[0]),
        "hour": int(user_details["time_of_birth"].split(":")[0]),
        "min": int(user_details["time_of_birth"].split(":")[1]),
        "lat": user_details.get("lat"),  # Hardcoded Value
        "lon": user_details.get("long"),  # Hardcoded Value
        "tzone": user_details.get("tzone", 5.0)
    }


    async with httpx.AsyncClient() as client:
        #Astro Details
        astro_resp = await client.post(f"{BASE_URL}/astro_details", json=payload, headers=headers)
        if astro_resp.status_code != 200 or not astro_resp.json():
            raise HTTPException(status_code=astro_resp.status_code, detail="Failed to fetch astro_details")
        astro_data = astro_resp.json()

        #Planet Positions
        planets_resp = await client.post(f"{BASE_URL}/planets", json=payload, headers=headers)
        if planets_resp.status_code != 200 or not planets_resp.json():
            raise HTTPException(status_code=planets_resp.status_code, detail="Failed to fetch planets data")
        planets_data = {p['name']: p for p in planets_resp.json()}  # convert to dict for easy lookup

        #Current Vimshottari Dasha
        dasha_resp = await client.post(f"{BASE_URL}/current_vdasha", json=payload, headers=headers)
        if dasha_resp.status_code != 200 or not dasha_resp.json():
            dashas_data = {}
        else:
            dashas_data = dasha_resp.json()

    moon_sign = planets_data.get("Moon", {}).get("sign", "")
    # Combine into final astrology object
    astrology_data = {
        "name": user_details['name'],
        "date_of_birth": user_details["date_of_birth"],
        "time_of_birth": user_details["time_of_birth"],
        "lat": user_details.get("lat"),
        "long": user_details.get("long"),
        "astro_details": astro_data,
        "ascendant": astro_data.get("ascendant", ""),
        "sun_sign": astro_data.get("sign", ""),        
        "moon_sign": moon_sign,
        "planet_positions": planets_data,
        "dashas": dashas_data,
    }

    return astrology_data


async def get_or_fetch_astrology_data(user_id: int, user_details: dict):
    """
    Fetch astrology data for a user from DB if exists.
    If not, call astrology API, save the result, and return it.
    """
    try:
        # 1️⃣ Check if data exists in DB
        existing = await db.astrological_information.find_one({"user_id": user_id})
        if existing:
            return {
                "name": user_details['name'],
                "date_of_birth": user_details["date_of_birth"],
                "time_of_birth": user_details["time_of_birth"],
                "lat": user_details.get("lat"),
                "long": user_details.get("long"),
                "gender": user_details["gender"],
                "ascendant": existing["astro_data"].get("ascendant", ""),
                "sun_sign": existing["astro_data"].get("sun_sign", ""),
                "moon_sign": existing["planets_data"].get("Moon", {}).get("sign", ""),
                "planet_positions": existing["planets_data"],
                "dashas": existing["dashas_data"]
            }

        # 2️⃣ If not exists, call astrology API
        astrology_data = await fetch_kundli(user_details)

        # 3️⃣ Save into DB
        await save_astrology_data(user_id, astrology_data)

        return astrology_data

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting astrology data: {str(e)}"
        )

async def fetch_user_details(id):
    try:
        user = await db.users.find_one({"_id": ObjectId(id)})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User Not Found"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user details: {str(e)}"
        )


async def get_category_from_question(question):
    category_list = await fetch_categories()
    system_prompt = f"""
    You have to fetch the category from the question given to you. These are the only categories you have to choose from:
    {category_list}

    Just give a one word answer. For Example, "When would I become a millionaire?". You just have to answer "career".
    """

    messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": question}
]
    response = openai_client.chat.completions.create(
        model='gpt-4o-mini',
        messages=messages,
        temperature=0,
        max_tokens=500
    )

    return  response.choices[0].message.content


async def save_chat_in_db(user_id, role, message, category):
    await db.chat_history.insert_one({
        "user_id": ObjectId(user_id),
        "role": role,
        "message": message,
        "category": category,
        "created_at": datetime.utcnow()
    })


async def get_astrology_prediction(user_astrology_data: dict, user_question: str, user_id: str):
    category = await get_category_from_question(user_question)
    astrology_summary = "\n".join(f"{key}: {value}" for key, value in user_astrology_data.items())

    system_prompt_doc = await db.system_prompts.find_one({"category": category})

    if not system_prompt_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Prompt Found Against This Category")
    
    system_prompt_text = system_prompt_doc["prompt"]
    system_prompt = f"""
    {system_prompt_text}

    IMPORTANT RULES:
    - The astrological data below belongs to the **same user who is chatting with you**.
    - ALWAYS speak directly to the user.
    - NEVER speak in third person (avoid: 'Nisha's chart', 'their chart', etc.).
    - ALWAYS give insights as if you are advising the user directly.

    Astrological Data:
    {astrology_summary}
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Here is my astrological data:\n{astrology_summary}\n\nPlease answer this question based on my data:\n{user_question}"}
    ]

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.2,
        max_tokens=1000
    )

    await asyncio.gather(
    save_chat_in_db(user_id, "user", user_question, category),
    save_chat_in_db(user_id, "assistant", response.choices[0].message.content, category)    
    )

    return response.choices[0].message.content, category
