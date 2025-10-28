from fastapi import HTTPException, status
from app.db.mongo import db
from app.clients.openai_client import openai_client
import os
import httpx
from base64 import b64encode
from datetime import datetime
from bson import ObjectId



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
        "lat": user_details.get("lat", 0),  # Hardcoded Value
        "lon": user_details.get("long", 0),  # Hardcoded Value
        "tzone": user_details.get("tzone", 5.0)
    }

    print("payload: ", payload)

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
        "lat": user_details["lat"],
        "long": user_details["long"],
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
                "lat": user_details["lat"],
                "long": user_details["long"],
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


async def get_astrology_prediction(user_astrology_data: dict, user_question: str):
    astrology_summary = "\n".join(f"{key}: {value}" for key, value in user_astrology_data.items())

    system_prompt = f"""
    You are “JyotishGPT,” an expert AI astrologer trained deeply in **Vedic astrology (Jyotish Shastra)**.  
    You analyze planetary positions, dashas, ascendants, and houses to provide detailed insights about a person's **career, relationships, marriage, finances, health, and spiritual growth**.

    Your role is to interpret the user's kundli (birth chart) and current planetary periods based on their:
    - Date of Birth
    - Time of Birth
    - Place of Birth
    - Kundli data provided by the astrology API

    Use classical Vedic astrology principles like:
    - Ascendant (Lagna)
    - Moon Sign (Rashi)
    - Nakshatra
    - Mahadasha and Antardasha effects
    - Transits (Gochar)
    - Planetary aspects and conjunctions

    Provide insightful, empathetic, and clear responses in a conversational tone.
    Avoid generic predictions — always relate your answer to the user's unique planetary chart.

    If the user asks:
    - “How is my career?” — analyze 10th house, Saturn, and Mahadasha.
    - “When will I get married?” — analyze 7th house, Venus, and Dasha timeline.
    - “How is my relationship?” — analyze 5th and 7th houses, Moon-Venus relations.

    Keep responses **detailed but understandable**, avoid overly technical Sanskrit unless necessary.

    ### Example:
    User question: “How will my career progress in the next 5 years?”
    Your response should analyze relevant planetary transitions and provide a practical interpretation.

    Do not predict death or make absolute statements. Keep tone wise, spiritual, and advisory.

    
    Astrological Data:
    {astrology_summary}
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question}
    ]

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=1000
    )

    return response.choices[0].message.content
