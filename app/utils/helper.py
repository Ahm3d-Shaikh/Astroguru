from fastapi import HTTPException, status
from app.db.mongo import db
from app.clients.openai_client import openai_client
from app.clients.gemini_client import client
from google.genai import types
import os
import httpx
from base64 import b64encode
from datetime import datetime
from fpdf import FPDF
from bson import ObjectId
import json
from app.services.prompt_service import fetch_categories
import asyncio
import io
import re
from app.clients.aws import s3_client, S3_BUCKET

ASTRO_API_USER_ID = os.getenv("ASTROLOGY_API_USER_ID")
ASTRO_API_KEY = os.getenv("ASTROLOGY_API_KEY")

BASE_URL = "https://json.astrologyapi.com/v1"


async def save_astrology_data(user_id: str, profile_id: str, astrology_data: dict):
    try:
        record = {
            "user_id": ObjectId(user_id),
            "profile_id": ObjectId(profile_id),
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
            {"user_id": user_id, "profile_id": profile_id},
            {"$set": record},
            upsert=True
        )
        return True
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving astrology data: {str(e)}"
        )


def normalize_chart(chart_data: list):
    if not chart_data:
        return {
            "ascendant": None,
            "houses": []
        }

    ascendant = chart_data[0].get("sign_name")

    houses = []
    for idx, house in enumerate(chart_data):
        houses.append({
            **house,
            "house_number": idx + 1
        })

    return {
        "ascendant": ascendant,
        "houses": houses
    }


async def fetch_chart_image(id, chart):
    try:
        user_details = await fetch_user_details(id)
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
            "tzone": user_details.get("tzone", 5.0),
            "image_type": "png"
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{BASE_URL}/horo_chart_image/{chart}",
                json=payload,
                headers=headers
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail="Failed to fetch horoscope chart image"
            )
        chart = response.json()
        return chart["chart_url"]
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching chart image from astrology api: {str(e)}"
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


    D_CHART_IDS = ["d1","d2","d3","d4","d5","d6","d7","d8","d9","d10","d11","d12","d16","d20","d24","d27","d30","d40","d45","d60"]

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
                normalized = normalize_chart(r.json())
                return chart_id, normalized
            return chart_id, {"error": "Failed to fetch"}

        d_tasks = [fetch_chart(cid) for cid in D_CHART_IDS]
        d_results = await asyncio.gather(*d_tasks)

        all_d_charts = {k: v for k, v in d_results}


    planets_data = {p['name']: p for p in results["planets"]}
    moon_sign = planets_data.get("Moon", {}).get("sign", "")
    sun_sign = planets_data.get("Sun", {}).get("sign", "")

    astrology_data = {
        "name": user_details["name"],
        "date_of_birth": user_details["date_of_birth"],
        "time_of_birth": user_details["time_of_birth"],
        "lat": user_details.get("lat"),
        "long": user_details.get("long"),

        "astro_details": results["astro"],
        "ascendant": results["astro"].get("ascendant", ""),
        "sun_sign": sun_sign,
        "moon_sign": moon_sign,

        "planet_positions": planets_data,

        "current_vdasha": results["current_vdasha"],
        "current_vdasha_all": results["current_vdasha_all"],
        "major_yogini_dasha": results["major_yogini"],
        "current_yogini_dasha": results["current_yogini"],

        "horoscope_charts": all_d_charts
    }

    return astrology_data


async def get_or_fetch_astrology_data(user_id: str, profile_id: str, profile_details: dict):
    """
    Fetch astrology data for a user from DB if exists.
    If not, call astrology API, save the result, and return it.
    """
    try:
        # 1️⃣ Check if data exists in DB
        existing = await db.astrological_information.find_one({"user_id": ObjectId(user_id), "profile_id": ObjectId(profile_id)})
        if existing:
            return {
                "name": profile_details['name'],
                "date_of_birth": profile_details["date_of_birth"],
                "time_of_birth": profile_details["time_of_birth"],
                "lat": profile_details.get("lat"),
                "long": profile_details.get("long"),
                "place_of_birth": profile_details.get("place_of_birth"),
                "gender": profile_details["gender"],
                "ascendant": existing["astro_data"].get("ascendant", ""),
                "sun_sign": existing["planets_data"].get("Sun", {}).get("sign", ""),
                "moon_sign": existing["planets_data"].get("Moon", {}).get("sign", ""),
                "planet_positions": existing["planets_data"],
                "current_vdasha": existing["current_vdasha_data"],
                "current_vdasha_all": existing["current_vdasha_all_data"],
                "current_yogini_dasha": existing["current_yogini_dasha_data"],
                "major_yogini_dasha": existing["major_yogini_dasha_data"],
                "horoscope_charts": existing["horoscope_charts_data"]
            }

        # 2️⃣ If not exists, call astrology API
        astrology_data = await fetch_kundli(profile_details)

        # 3️⃣ Save into DB
        await save_astrology_data(user_id, profile_id, astrology_data)

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

async def fetch_profile_details(user_id, profile_id):
    profile = await db.user_profiles.find_one({
        "_id": ObjectId(profile_id),
        "user_id": ObjectId(user_id)
    })

    if not profile:
        raise HTTPException(status_code=404, detail="Profile Not Found")
    return profile


async def get_category_from_question(question):
    category_list = await fetch_categories()
    system_prompt = f"""
    You are a strict classifier. Your job is to choose ONE category for the question.

    These are the ONLY allowed categories:
    {category_list}

    Rules:
    - Reply with EXACTLY one word: the category name.
    - Do NOT explain.
    - Do NOT add punctuation or quotes.
    - If the question fits multiple categories, choose the BEST one.
    Example:
    Q: "When would I become a millionaire?"
    A: career
    """
    
    config = types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=64,
        system_instruction=system_prompt,
    )

    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=question,
        config=config,
    )

    reply = response.text.strip().strip('"').strip("'")  # <-- normalize
    return reply


async def save_chat_in_db(user_id, profile_id, role, conversation_id,  message, category):
    await db.chat_history.insert_one({
        "user_id": ObjectId(user_id),
        "profile_id": ObjectId(profile_id),
        "role": role,
        "conversation_id": ObjectId(conversation_id),
        "message": message,
        "category": category,
        "created_at": datetime.utcnow()
    })


async def create_conversation(user_id, profile_id, category, first_user_message):
    result = await db.conversations.insert_one({
        "user_id": ObjectId(user_id),
        "profile_id": ObjectId(profile_id),
        "category": category,
        "title": first_user_message[:50],
        "created_at": datetime.utcnow()
    })

    return str(result.inserted_id)


async def get_astrology_prediction(user_astrology_data: dict, user_question: str, user_id: str, profile_id: str, conversation_id=None):
    category = await get_category_from_question(user_question)
    astrology_summary = "\n".join(f"{key}: {value}" for key, value in user_astrology_data.items())

    if not conversation_id:
        conversation_id = await create_conversation(user_id, profile_id, category, user_question)
    
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
    - Never respond to anything unrelated to astrology, predictions, signs or lucky factors.
    - ALWAYS mention the chart and house when referencing planets (You need to look in "horoscope_charts" in astrology_summary to look for these charts)
    - ALWAYS use all the 'horoscopic_charts' as context when replying.
    - ALWAYS provide astrological references in readable text format. e.g.,
        "Based on D1 chart, Sun is in Sagittarius in house 1", not arrays.
    """
    
    past_messages = await db.chat_history.find({
        "conversation_id": ObjectId(conversation_id),
        "profile_id": ObjectId(profile_id)
    }).to_list(length=20)  
    
    history_text = "\n".join(
        [f"{msg['role']}: {msg['message']}" for msg in past_messages]
    )
    
    contents = [
        f"Chat History: \n{history_text}\n\n"
        f"Here is my astrological data:\n{astrology_summary}\n\n"
        f"Please answer this question based on my data:\n{user_question}"
    ]


    config = types.GenerateContentConfig(
        temperature = 0.2,
        max_output_tokens = 1000,
        system_instruction = system_prompt
    )

    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=contents,
        config=config,
    )

    reply = response.text

    await asyncio.gather(
    save_chat_in_db(user_id, profile_id, "user", conversation_id, user_question, category),
    save_chat_in_db(user_id, profile_id, "assistant", conversation_id, reply, category)    
    )

    return reply, category, conversation_id


def markdown_to_plain(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r'(^|\n)#{1,6}\s*(.+)', r'\1\n\2\n', text)

    text = re.sub(r'(\*\*|__|\*)', '', text)

    text = re.sub(r'^[\*\-\+]\s+', '- ', text, flags=re.MULTILINE)

    return text.strip()


async def generate_report_helper(user_details, astrology_data, user_report, pdf_report):
    astrology_summary = "\n".join(f"{key}: {value}" for key, value in astrology_data.items())
    prompt = user_report.get("prompt", "You are an astrology report generator.")
    contents = [
        f"Here is my astrological data:\n{astrology_summary}\n\n",
        f"Here's my personal data: {user_details}\n\n",
        "Generate a detailed, warm, human-sounding astrology report."
    ]

    config = types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=2000,
        system_instruction=prompt,
    )

    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=contents,
        config=config,
    )
    
    report_text = response.text
    if not pdf_report or pdf_report is False:
        return report_text

    safe_text = markdown_to_plain(report_text)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.add_page()

    pdf.add_font(
        "NotoSans",
        "",
        "app/deps/fonts/NotoSans-Regular.ttf",
        uni=True,
    )
    pdf.add_font(
        "NotoSans",
        "I",
        "app/deps/fonts/NotoSans-Italic.ttf",
        uni=True,
    )
    pdf.add_font(
        "NotoSans",
        "B",
        "app/deps/fonts/NotoSans-Bold.ttf",
        uni=True,
    )

    # Title
    pdf.set_font("NotoSans", "B", 16)
    pdf.cell(0, 10, "Astrology Report", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("NotoSans", "", 12)

    paragraphs = safe_text.split("\n")
    for para in paragraphs:
        para = para.strip()
        if not para:
            pdf.ln(5)  
            continue

        pdf.multi_cell(0, 8, para)
        pdf.ln(2)

    pdf.ln(5)

    pdf.set_y(-20)  
    pdf.set_font("NotoSans", "I", 10)
    pdf.cell(
        0,
        10,
        f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        align="R",
    )

    pdf_raw = pdf.output(dest="S")
    if isinstance(pdf_raw, str):
        pdf_bytes = pdf_raw.encode("latin1")
    else:
        pdf_bytes = bytes(pdf_raw)

    pdf_buffer = io.BytesIO(pdf_bytes)
    pdf_buffer.seek(0)

    filename = f"astrology_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    s3_key = f"astrology_reports/{filename}"

    s3_client.upload_fileobj(
        Fileobj=pdf_buffer,
        Bucket=S3_BUCKET,
        Key=s3_key,
        ExtraArgs={"ContentType": "application/pdf"},
    )

    file_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{s3_key}"
    return file_url


async def fetch_user_report(id, user_id, profile_id):
    try:
        user_report = await db.user_reports.find_one(
            {"user_id": ObjectId(user_id), "profile_id": ObjectId(profile_id), "report_id": ObjectId(id)}
        )

        if not user_report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No Downloaded Reports Found For The User"
            )

        report_id = user_report["report_id"]
        report = await db.reports.find_one(
            {"_id": report_id}
        )

        return report

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user report: {str(e)}"
        )
    


async def generate_predictions_for_homepage(user_details, astrology_data):
    try:
        astrology_summary = "\n".join(f"{key}: {value}" for key, value in astrology_data.items())
        prediction_prompt_doc = await db.predictions.find_one({"name": "Dashboard Overview"})
        prompt = prediction_prompt_doc["prompt"]
        

        contents = [
            f"Here is my astrological data:\n{astrology_summary}\n\n",
            f"Here's my personal data: {user_details}\n\n",
            "Give me predictions about me. Return a JSON object with two keys:\n"
            "1. 'text' -> containing your written predictions in plain text.\n"
            "2. 'prediction_dict' -> a Python dictionary containing:\n"
            """{
                "lucky_number": <int>,
                "lucky_color": "<string>",
                "lucky_color_hex": <string> For Example: #008000
                "lucky_time": "<string>" For Example: 03:00 AM,
                "name": "<string>",
                "sun_sign": "<string>",
                "element": "<string>",
                "moon_sign": "<string>",
                "polarity": "<string>",
                "modality": "<string>"
            }"""

        ]


        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=1000,
            system_instruction=prompt,
        )

        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=config,
        )


        content = response.text
        content_cleaned = re.sub(r"^```json\s*|```$", "", content.strip(), flags=re.MULTILINE)

        try:
            data = json.loads(content_cleaned)
            text_output = data.get("text", "")
            prediction_dict = data.get("prediction_dict", {})
        except json.JSONDecodeError:
            text_output = content
            prediction_dict = {}

        prediction_dict["zodiac_sign"] = get_zodiac_sign(user_details.get("date_of_birth"))
        return text_output, prediction_dict
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while generating predictions for homepage: {str(e)}"
        )


def get_zodiac_sign(date_of_birth: str):
    try:
        dob = datetime.strptime(date_of_birth, "%Y-%m-%d")
    except Exception:
        return None
    
    day = dob.day
    month = dob.month
    
    if (month == 12 and day >= 22) or (month == 1 and day <= 19):
        return "Capricorn"
    elif (month == 1 and day >= 20) or (month == 2 and day <= 18):
        return "Aquarius"
    elif (month == 2 and day >= 19) or (month == 3 and day <= 20):
        return "Pisces"
    elif (month == 3 and day >= 21) or (month == 4 and day <= 19):
        return "Aries"
    elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
        return "Taurus"
    elif (month == 5 and day >= 21) or (month == 6 and day <= 20):
        return "Gemini"
    elif (month == 6 and day >= 21) or (month == 7 and day <= 22):
        return "Cancer"
    elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
        return "Leo"
    elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
        return "Virgo"
    elif (month == 9 and day >= 23) or (month == 10 and day <= 22):
        return "Libra"
    elif (month == 10 and day >= 23) or (month == 11 and day <= 21):
        return "Scorpio"
    else:
        return "Sagittarius"
