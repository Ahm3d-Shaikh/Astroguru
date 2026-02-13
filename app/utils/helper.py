from fastapi import HTTPException, status
from app.db.mongo import db
from app.clients.openai_client import openai_client
from app.clients.gemini_client import client
from google.genai import types
import os
import httpx
from base64 import b64encode
from datetime import datetime, timezone
from fpdf import FPDF
from bson import ObjectId
import json
from app.services.prompt_service import fetch_categories
import asyncio
import io
import re
from app.clients.aws import s3_client, S3_BUCKET
from app.services.subscription_service import deduct_user_credits

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
            "arudha_lagna": astrology_data.get("arudha_lagna", {}),
            "indu_lagna": astrology_data.get("indu_lagna", {}),
            "karakamsha_lagna": astrology_data.get("karakamsha_lagna", {}),
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


async def fetch_chart_image(id, chart, profile_id: str | None = None):
    try:
        if profile_id == id:
            profile_details = await fetch_user_details(id)
        else:
            profile_details = await fetch_profile_details(id, profile_id)
        auth_header = b64encode(f"{ASTRO_API_USER_ID}:{ASTRO_API_KEY}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/json"
        }

        payload = {
            "day": int(profile_details["date_of_birth"].split("-")[2]),
            "month": int(profile_details["date_of_birth"].split("-")[1]),
            "year": int(profile_details["date_of_birth"].split("-")[0]),
            "hour": int(profile_details["time_of_birth"].split(":")[0]),
            "min": int(profile_details["time_of_birth"].split(":")[1]),
            "lat": profile_details.get("lat"),  
            "lon": profile_details.get("long"), 
            "tzone": profile_details.get("tzone", 5.5),
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
        "tzone": user_details.get("tzone", 5.5)
    }


    D_CHART_IDS = ["d1","d2","d3","d4","d5","d7","d8","d9","d10","d12","d16","d20","d24","d27","d30","d40","d45","d60"]

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

    astrology_data["arudha_lagna"] = calculate_arudha_lagna(astrology_data)
    astrology_data["indu_lagna"] = calculate_indu_lagna(astrology_data)
    astrology_data["karakamsha_lagna"] = calculate_karakamsha_lagna(astrology_data)
    astrology_data["horoscope_charts"]["d6"] = calculate_d6_chart(astrology_data)
    astrology_data["horoscope_charts"]["d11"] = calculate_d11_chart(astrology_data)

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
                "horoscope_charts": existing["horoscope_charts_data"],
                "arudha_lagna": existing["arudha_lagna"],
                "indu_lagna": existing["indu_lagna"],
                "karakamsha_lagna": existing["karakamsha_lagna"]
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
    profile = None
    if user_id == profile_id:
        profile = await db.users.find_one({
            "_id": ObjectId(user_id)
        })
    else:
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

    reply = response.text.strip().strip('"').strip("'").lower()  # <-- normalize
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
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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
    - Today's date is {today}. Use it for time-based calculations.
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
    save_chat_in_db(user_id, profile_id, "assistant", conversation_id, reply, category),
    deduct_user_credits(user_id, 1, "1 Chat Consumed")  
    )

    return reply, category, conversation_id


def markdown_to_plain(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r'(^|\n)#{1,6}\s*(.+)', r'\1\n\2\n', text)

    text = re.sub(r'(\*\*|__|\*)', '', text)

    text = re.sub(r'^[\*\-\+]\s+', '- ', text, flags=re.MULTILINE)

    return text.strip()



async def save_user_report(user_id, profile_id, report_id, file_url, report_text):
    result = await db.user_reports.update_one(
        {   "user_id": ObjectId(user_id),
            "profile_id": ObjectId(profile_id),
            "report_id": ObjectId(report_id)
        },
        {
            "$set": {
                "file_url": file_url,
                "report_text": report_text
            }
        }
    )

    return result

async def generate_report_helper(user_details, astrology_data, user_report, pdf_report, user_id, profile_id):
    astrology_summary = "\n".join(f"{key}: {value}" for key, value in astrology_data.items())
    prompt = user_report.get("prompt", "You are an astrology report generator.")
    report_name = user_report.get("name", "Astrology Report")
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

    await save_user_report(
        user_id,
        profile_id,
        user_report["_id"],
        None,          # file_url (updated later if PDF exists)
        report_text
    )

    chat_doc = {
        "report_id": user_report["_id"],
        "user_id": ObjectId(user_id),
        "profile_id": ObjectId(profile_id),
        "messages": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    await db.report_chats.insert_one(chat_doc)
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
    pdf.cell(0, 10, report_name, ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("NotoSans", "", 12)

    paragraphs = safe_text.split("\n")
    lines = report_text.split("\n")

    for line in lines:
        line = line.strip()

        if not line:
            pdf.ln(5)
            continue

        # H1 / H2 style (## Heading)
        if line.startswith("## "):
            pdf.set_font("NotoSans", "B", 15)
            pdf.multi_cell(0, 10, line.replace("## ", ""))
            pdf.ln(4)
            pdf.set_font("NotoSans", "", 12)
            continue

        # H3 style (### Heading)
        if line.startswith("### "):
            pdf.set_font("NotoSans", "B", 13)
            pdf.multi_cell(0, 8, line.replace("### ", ""))
            pdf.ln(3)
            pdf.set_font("NotoSans", "", 12)
            continue

        # Bold inline text (**text**)
        bold_parts = re.split(r'(\*\*.*?\*\*)', line)

        for part in bold_parts:
            if part.startswith("**") and part.endswith("**"):
                pdf.set_font("NotoSans", "B", 12)
                pdf.write(8, part.replace("**", ""))
                pdf.set_font("NotoSans", "", 12)
            else:
                pdf.write(8, part)

        pdf.ln(8)

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
    await save_user_report(user_id, profile_id, user_report["_id"], file_url, report_text)
    chat_doc = {
        "report_id": user_report["_id"],
        "user_id": ObjectId(user_id),
        "profile_id": ObjectId(profile_id),
        "messages": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    await db.report_chats.insert_one(chat_doc)
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
        zodiac_sign = get_zodiac_sign(user_details.get("date_of_birth"))
        prediction_dict["zodiac_sign"] = zodiac_sign
        prediction_dict["sun_sign"] = zodiac_sign
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
    


ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

SIGN_TO_INDEX = {sign: i for i, sign in enumerate(ZODIAC_SIGNS)}
INDEX_TO_SIGN = {i: sign for i, sign in enumerate(ZODIAC_SIGNS)}

PLANET_KALA = {
    "Sun": 30,
    "Moon": 16,
    "Venus": 12,
    "Jupiter": 10,
    "Mercury": 8,
    "Mars": 6,
    "Saturn": 1,
    "Rahu": 0,
    "Ketu": 0
}

SIGN_LORD = {
    "Aries": "Mars",
    "Taurus": "Venus",
    "Gemini": "Mercury",
    "Cancer": "Moon",
    "Leo": "Sun",
    "Virgo": "Mercury",
    "Libra": "Venus",
    "Scorpio": "Mars",
    "Sagittarius": "Jupiter",
    "Capricorn": "Saturn",
    "Aquarius": "Saturn",
    "Pisces": "Jupiter"
}

def normalize_sign_index(index: int) -> int:
    return index % 12

def count_sign_distance(from_sign: str, to_sign: str) -> int:
    start = SIGN_TO_INDEX[from_sign]
    end = SIGN_TO_INDEX[to_sign]
    return (end - start) % 12 + 1

def calculate_arudha_lagna(astrology_data: dict) -> str:
    ascendant = astrology_data["ascendant"]
    lagna_index = SIGN_TO_INDEX[ascendant]

    lagna_lord = astrology_data["planet_positions"]["Ascendant"]["signLord"]

    lagna_lord_sign = astrology_data["planet_positions"][lagna_lord]["sign"]
    lord_index = SIGN_TO_INDEX[lagna_lord_sign]

    distance = count_sign_distance(ascendant, lagna_lord_sign)

    preliminary_index = normalize_sign_index(lord_index + distance - 1)
    preliminary_sign = INDEX_TO_SIGN[preliminary_index]

    house_from_lagna = (preliminary_index - lagna_index) % 12 + 1

    if house_from_lagna == 1:
        final_index = normalize_sign_index(lagna_index + 9)
        return INDEX_TO_SIGN[final_index]

    if house_from_lagna == 7:
        final_index = normalize_sign_index(preliminary_index + 9)
        return INDEX_TO_SIGN[final_index]

    return preliminary_sign

def calculate_indu_lagna(astrology_data: dict) -> str:
    ascendant = astrology_data["ascendant"]
    moon_sign = astrology_data["moon_sign"]

    asc_index = SIGN_TO_INDEX[ascendant]
    moon_index = SIGN_TO_INDEX[moon_sign]

    ninth_from_asc_index = normalize_sign_index(asc_index + 8)
    ninth_from_asc_sign = INDEX_TO_SIGN[ninth_from_asc_index]

    ninth_from_moon_index = normalize_sign_index(moon_index + 8)
    ninth_from_moon_sign = INDEX_TO_SIGN[ninth_from_moon_index]

    lagna_9_lord = SIGN_LORD[ninth_from_asc_sign]
    moon_9_lord = SIGN_LORD[ninth_from_moon_sign]

    value_1 = PLANET_KALA.get(lagna_9_lord, 0)
    value_2 = PLANET_KALA.get(moon_9_lord, 0)

    total = value_1 + value_2

    remainder = total % 12
    remainder = 12 if remainder == 0 else remainder

    indu_index = normalize_sign_index(moon_index + remainder - 1)

    return INDEX_TO_SIGN[indu_index]


def calculate_atmakaraka(astrology_data: dict) -> str:
    classical_planets = [
        "Sun", "Moon", "Mars",
        "Mercury", "Jupiter", "Venus", "Saturn"
    ]

    max_degree = -1
    atmakaraka = None

    for planet in classical_planets:
        planet_data = astrology_data["planet_positions"].get(planet)
        if not planet_data:
            continue

        degree = planet_data.get("normDegree", 0)

        if degree > max_degree:
            max_degree = degree
            atmakaraka = planet

    return atmakaraka


def calculate_navamsa_sign(sign: str, degree: float) -> str:
    sign_index = SIGN_TO_INDEX[sign]

    navamsa_size = 30 / 9 
    navamsa_number = int(degree // navamsa_size)

    d9_index = normalize_sign_index(sign_index * 9 + navamsa_number)
    return INDEX_TO_SIGN[d9_index]


def calculate_karakamsha_lagna(astrology_data: dict) -> str:
    ak = calculate_atmakaraka(astrology_data)

    if not ak:
        raise ValueError("Atmakaraka could not be determined")

    ak_data = astrology_data["planet_positions"][ak]
    ak_sign = ak_data["sign"]
    ak_degree = ak_data["normDegree"]

    karakamsha_lagna = calculate_navamsa_sign(ak_sign, ak_degree)

    return karakamsha_lagna



SIGN_ORDER = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

SIGN_NAME_TO_NUM = {name: i + 1 for i, name in enumerate(SIGN_ORDER)}
SIGN_NUM_TO_NAME = {i + 1: name for i, name in enumerate(SIGN_ORDER)}


def build_indu_lagna_chart(indu_lagna, d1_chart):
    if isinstance(indu_lagna, str):
        indu_lagna_num = SIGN_NAME_TO_NUM[indu_lagna.capitalize()]
    else:
        indu_lagna_num = indu_lagna

    indu_lagna_name = SIGN_NUM_TO_NAME[indu_lagna_num]

    indu_chart = {
        "indu_lagna": indu_lagna_name,
        "houses": []
    }

    for house in d1_chart["houses"]:
        sign_num = house["sign"]

        house_number = ((sign_num - indu_lagna_num) % 12) + 1

        indu_chart["houses"].append({
            "house_number": house_number,
            "sign": sign_num,
            "sign_name": SIGN_NUM_TO_NAME[sign_num],
            "planet": house["planet"],
            "planet_small": house["planet_small"],
            "planet_degree": house.get("planet_degree", [])
        })

    # Sort by Indu Lagna house order (1 → 12)
    indu_chart["houses"].sort(key=lambda x: x["house_number"])

    return indu_chart


def build_karakamsha_chart(karakamsha_lagna, d1_chart):
    """
    Build Karakamsha chart by rotating the D1 chart.

    Rules (as per client):
    - Karakamsha Lagna is derived from D9 (already computed)
    - D9 is NOT used for planet placement
    - Take D1 chart and remap house numbers
    - Preserve all planetary signs and groupings
    """

    # Normalize Karakamsha Lagna
    if isinstance(karakamsha_lagna, str):
        karakamsha_num = SIGN_NAME_TO_NUM[karakamsha_lagna.capitalize()]
    else:
        karakamsha_num = karakamsha_lagna

    karakamsha_chart = {
        "karakamsha_lagna": SIGN_NUM_TO_NAME[karakamsha_num],
        "houses": []
    }

    for house in d1_chart["houses"]:
        sign_num = house["sign"]

        # Rotate houses
        house_number = ((sign_num - karakamsha_num) % 12) + 1

        karakamsha_chart["houses"].append({
            "house_number": house_number,
            "sign": sign_num,
            "sign_name": SIGN_NUM_TO_NAME[sign_num],
            "planet": house.get("planet", []),
            "planet_small": house.get("planet_small", []),
            "planet_degree": house.get("planet_degree", [])
        })

    # Sort houses from 1 → 12
    karakamsha_chart["houses"].sort(key=lambda x: x["house_number"])

    return karakamsha_chart


def build_arudha_lagna_chart(arudha_lagna, d1_chart):
    """
    Build Arudha Lagna chart using D1 positions.

    Parameters:
        arudha_lagna (str | int): Final Arudha Lagna sign
        d1_chart (dict): D1 chart data

    Returns:
        dict: Arudha Lagna chart
    """

    # Normalize Arudha Lagna
    if isinstance(arudha_lagna, str):
        al_sign_num = SIGN_NAME_TO_NUM[arudha_lagna.capitalize()]
    else:
        al_sign_num = arudha_lagna

    al_sign_name = SIGN_NUM_TO_NAME[al_sign_num]

    arudha_chart = {
        "arudha_lagna": al_sign_name,
        "houses": []
    }

    # Build 12-house sign structure
    for i in range(12):
        sign_num = ((al_sign_num - 1 + i) % 12) + 1

        arudha_chart["houses"].append({
            "house_number": i + 1,
            "sign": sign_num,
            "sign_name": SIGN_NUM_TO_NAME[sign_num],
            "planet": [],
            "planet_small": [],
            "planet_degree": []
        })

    # Index houses by sign
    sign_to_house = {
        house["sign"]: house for house in arudha_chart["houses"]
    }

    # Place planets using D1 sign positions
    for house in d1_chart["houses"]:
        sign_num = house["sign"]

        target_house = sign_to_house.get(sign_num)
        if not target_house:
            continue

        target_house["planet"].extend(house.get("planet", []))
        target_house["planet_small"].extend(house.get("planet_small", []))
        target_house["planet_degree"].extend(house.get("planet_degree", []))

    return arudha_chart


def sign_to_house(sign_num, asc_sign_num):
    house = (sign_num - asc_sign_num) % 12 + 1
    return house



def calculate_d6_chart(astrology_data):
    signs = [
        'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
        'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
    ]

    sign_to_num = {s: i + 1 for i, s in enumerate(signs)}
    num_to_sign = {i + 1: s for i, s in enumerate(signs)}

    def planet_to_d6(planet):
        full_deg = planet['fullDegree']
        sign_num = sign_to_num[planet['sign']]

        degree_in_sign = full_deg % 30
        part_number = int(degree_in_sign // 5) + 1  # 1–6

        anchor_num = (sign_num + 5) % 12 or 12
        d6_sign_num = (anchor_num + part_number - 2) % 12 + 1

        return d6_sign_num

    asc_data = astrology_data['planet_positions']['Ascendant']
    d6_asc_sign_num = planet_to_d6(asc_data)

    d6_chart = {i: [] for i in range(1, 13)}

    for planet, pdata in astrology_data['planet_positions'].items():
        if planet.upper() == 'ASCENDANT':
            continue

        d6_sign_num = planet_to_d6(pdata)
        house_num = sign_to_house(d6_sign_num, d6_asc_sign_num)
        d6_chart[house_num].append(planet.upper())

    d6_houses = []
    for h in range(1, 13):
        sign_num = (d6_asc_sign_num + h - 2) % 12 + 1
        d6_houses.append({
            "house_number": h,
            "sign": sign_num,
            "sign_name": num_to_sign[sign_num],
            "planet": d6_chart[h]
        })

    return {
        "ascendant": num_to_sign[d6_asc_sign_num],
        "houses": d6_houses
    }


def calculate_d11_chart(astrology_data):
    signs = [
        'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
        'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
    ]

    sign_to_num = {s: i + 1 for i, s in enumerate(signs)}
    num_to_sign = {i + 1: s for i, s in enumerate(signs)}

    PART_DEG = 30 / 11

    def planet_to_d11(planet):
        full_deg = planet['fullDegree']
        sign_num = sign_to_num[planet['sign']]

        degree_in_sign = full_deg % 30
        part_number = min(int(degree_in_sign // PART_DEG) + 1, 11)

        anchor_num = ((sign_num + 10 - 1) % 12) + 1
        d11_sign_num = ((anchor_num + part_number - 2) % 12) + 1

        return d11_sign_num

    asc_data = astrology_data['planet_positions']['Ascendant']
    d11_asc_sign_num = planet_to_d11(asc_data)

    d11_chart = {i: [] for i in range(1, 13)}

    for planet, pdata in astrology_data['planet_positions'].items():
        if planet.upper() == 'ASCENDANT':
            continue

        d11_sign_num = planet_to_d11(pdata)
        house_num = sign_to_house(d11_sign_num, d11_asc_sign_num)
        d11_chart[house_num].append(planet.upper())

    d11_houses = []
    for h in range(1, 13):
        sign_num = (d11_asc_sign_num + h - 2) % 12 + 1
        d11_houses.append({
            "house_number": h,
            "sign": sign_num,
            "sign_name": num_to_sign[sign_num],
            "planet": d11_chart[h]
        })

    return {
        "ascendant": num_to_sign[d11_asc_sign_num],
        "houses": d11_houses
    }


