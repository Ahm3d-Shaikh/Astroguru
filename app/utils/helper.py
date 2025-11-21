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
            "current_vdasha_data": astrology_data.get("current_vdasha", {}),
            "current_vdasha_all_data": astrology_data.get("current_vdasha_all", {}),
            "major_yogini_dasha_data": astrology_data.get("major_yogini_dasha",  {}),
            "current_yogini_dasha_data": astrology_data.get("current_yogini_dasha", {}),
            "horoscope_charts_data": astrology_data.get("horoscope_charts", {}),
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
        "lat": user_details.get("lat"),  
        "lon": user_details.get("long"), 
        "tzone": user_details.get("tzone", 5.0)
    }


    D_CHART_IDS = [1,2,3,4,5,6,7,8,9,10,11,12,16,20,24,27,30,40,45,60]

    async with httpx.AsyncClient() as client:

        main_calls = {
            "astro": client.post(f"{BASE_URL}/astro_details", json=payload, headers=headers),
            "planets": client.post(f"{BASE_URL}/planets", json=payload, headers=headers),
            "current_vdasha": client.post(f"{BASE_URL}/current_vdasha", json=payload, headers=headers),
            "current_vdasha_all": client.post(f"{BASE_URL}/current_vdasha_all", json=payload, headers=headers),
            "major_yogini": client.post(f"{BASE_URL}/major_yogini_dasha", json=payload, headers=headers),
            "current_yogini": client.post(f"{BASE_URL}/current_yogini_dasha", json=payload, headers=headers)
        }

        main_keys = list(main_calls.keys())
        main_responses = await asyncio.gather(*main_calls.values())

        results = {}
        for key, resp in zip(main_keys, main_responses):
            if resp.status_code != 200 or not resp.json():
                raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch {key}")
            results[key] = resp.json()

        async def fetch_chart(chart_id):
            r = await client.post(f"{BASE_URL}/horo_chart/{chart_id}", json=payload, headers=headers)
            if r.status_code == 200 and r.json():
                return f"D{chart_id}", r.json()
            return f"D{chart_id}", {"error": "Failed to fetch"}

        d_tasks = [fetch_chart(cid) for cid in D_CHART_IDS]
        d_results = await asyncio.gather(*d_tasks)

        all_d_charts = {k: v for k, v in d_results}


    planets_data = {p['name']: p for p in results["planets"]}
    moon_sign = planets_data.get("Moon", {}).get("sign", "")

    astrology_data = {
        "name": user_details["name"],
        "date_of_birth": user_details["date_of_birth"],
        "time_of_birth": user_details["time_of_birth"],
        "lat": user_details.get("lat"),
        "long": user_details.get("long"),

        "astro_details": results["astro"],
        "ascendant": results["astro"].get("ascendant", ""),
        "sun_sign": results["astro"].get("sign", ""),
        "moon_sign": moon_sign,

        "planet_positions": planets_data,

        "current_vdasha": results["current_vdasha"],
        "current_vdasha_all": results["current_vdasha_all"],
        "major_yogini_dasha": results["major_yogini"],
        "current_yogini_dasha": results["current_yogini"],

        "horoscope_charts": all_d_charts
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
                "place_of_birth": user_details.get("place_of_birth"),
                "gender": user_details["gender"],
                "ascendant": existing["astro_data"].get("ascendant", ""),
                "sun_sign": existing["astro_data"].get("sun_sign", ""),
                "moon_sign": existing["planets_data"].get("Moon", {}).get("sign", ""),
                "planet_positions": existing["planets_data"],
                "current_vdasha": existing["current_vdasha_data"],
                "current_vdasha_all": existing["current_vdasha_all_data"],
                "current_yogini_dasha": existing["current_yogini_dasha_data"],
                "major_yogini_dasha": existing["major_yogini_dasha_data"],
                "horoscope_charts": existing["horoscope_charts_data"]
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
    - Never respond to anything unrelated to astrology or predictions

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
