from fastapi import HTTPException, status, Body
from app.db.mongo import db
from bson import ObjectId
from datetime import datetime
from app.utils.helper import fetch_profile_details, get_or_fetch_astrology_data, markdown_to_plain, get_zodiac_sign
from app.services.astrology_service import generate_report_from_ai
from app.services.subscription_service import deduct_user_credits
from app.clients.gemini_client import client
from app.utils.mongo import convert_mongo
from app.core.concurrency import llm_semaphore
from app.utils.concurrency import generate_with_retry
from google.genai import types
from fpdf import FPDF
import io
import re
import json
from app.clients.aws import s3_client, S3_BUCKET


async def add_compatibility_prompt(payload):
    try:
        await db.compatibilities.insert_one({
            "type": payload.type,
            "prompt": payload.prompt,
            "is_comparison": payload.is_comparison,
            "created_at": datetime.utcnow()
        })
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding compatibility prompt in db: {str(e)}"
        )
    

async def fetch_compatibilities(is_comparison: bool, type: str):
    try:
        cursor = db.compatibilities.find({"is_comparison": is_comparison})
        compatibilities = await cursor.to_list(length=None)

        if not compatibilities:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No {type} Found")
        return compatibilities
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching compatibilities from db: {str(e)}"
        )
    

async def delete_compatibility_from_db(id):
    try:
        await db.compatibilities.delete_one({"_id": ObjectId(id)})
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting compatibility: {str(e)}"
        )
    

async def update_compatibility_by_id(update_data, id):
    try:
        object_id = ObjectId(id)
        result = await db.compatibilities.update_one({"_id": object_id}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compatibility not found")

        updated_compatibility = await db.compatibilities.find_one({"_id": object_id})
        updated_compatibility["_id"] = str(updated_compatibility["_id"])
        return updated_compatibility
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating compatibility: {str(e)}"
        )
    

async def fetch_compatibility_by_id(id):
    try:
        object_id = ObjectId(id)
        compatibility = await db.compatibilities.find_one({"_id": object_id})

        if not compatibility:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compatibility Not Found")
        
        compatibility["_id"] = str(compatibility["_id"])
        return compatibility
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching compatibility by id: {str(e)}"
        )


async def fetch_user_compatibility_reports(user_id):
    try:
        pipeline = [
            {"$match": {"user_id": ObjectId(user_id)}},
            {
                "$lookup": {
                    "from": "user_profiles", 
                    "localField": "profile_id",
                    "foreignField": "_id",
                    "as": "profiles"
                }
            },
            {
                "$lookup": {
                    "from": "compatibilities", 
                    "localField": "compatibility_id",
                    "foreignField": "_id",
                    "as": "compatibility"
                }
            },
            {"$unwind": {"path": "$compatibility", "preserveNullAndEmptyArrays": True}}
        ]
        cursor = db.user_compatibility_reports.aggregate(pipeline)
        user_reports = await cursor.to_list(length=None)
        if not user_reports:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Reports Not Found")
        
        for report in user_reports:
            for profile in report.get("profiles", {}):
                dob = profile.get("date_of_birth")
                profile["zodiac_sign"] = get_zodiac_sign(dob) if dob else None
        return user_reports
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user compatibility reports from db: {str(e)}"
        ) 

async def save_compatibility_user_report(user_id, compatibility_id, profile_id, is_comparison, file_url, report_text):
    profile_ids = [ObjectId(pid) if isinstance(pid, str) else pid for pid in profile_id]
    saved_report = await db.user_compatibility_reports.insert_one({
        "user_id": ObjectId(user_id),
        "profile_id": profile_ids,
        "compatibility_id": ObjectId(compatibility_id),
        "is_comparison": is_comparison,
        "pdf_report": file_url,
        "report_text": report_text,  
        "created_at": datetime.utcnow()
    })
    return saved_report

async def generate_compatibility_report(user_id, payload, pdf_report, report_type, language):
    try:
        profiles = dict()
        type = payload.type

        compatibility_doc = await db.compatibilities.find_one({"type": type, "is_comparison": payload.is_comparison})
        if not compatibility_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{report_type} Not Found")
        prompt = compatibility_doc["prompt"]
        type = compatibility_doc["type"]

        profile_ids = [ObjectId(pid) if isinstance(pid, str) else pid for pid in payload.profile_id]
        cursor = db.user_compatibility_reports.find({
            "user_id": ObjectId(user_id),
            "compatibility_id": ObjectId(compatibility_doc["_id"]),
            "pdf_report": {"$ne": None},
            "profile_id": {"$all": profile_ids, "$size": len(profile_ids)} 

        })
        existing_docs = await cursor.to_list(length=None)
        if existing_docs:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{report_type} Report For These Profiles Already Exists")
        
        for profile in payload.profile_id:
            profile_details = await fetch_profile_details(user_id, profile)
            astrology_data = await get_or_fetch_astrology_data(user_id, profile, profile_details)
            astrology_summary = "\n".join(f"{key}: {value}" for key, value in astrology_data.items())

            profile_key = str(profile)  

            profiles[profile_key] = {
                "profile_details": profile_details,
                "astrology_summary": astrology_summary
            }

        safe_profiles = convert_mongo(profiles)
        profiles_str = json.dumps(safe_profiles, indent=2) 

        contents = [
            f"Profiles:\n\n {profiles_str}",
            f"Number Of Profiles: {len(profiles.keys())}",
            f"Use all the profile details and astrological details to generate a detailed, warm, human-sounding {report_type} report.",
            f"Respond in {language} language."
        ]

        config = types.GenerateContentConfig(
        temperature = 1.0,
        max_output_tokens = 6000,
        system_instruction = prompt
        )
        async with llm_semaphore:
            response = await generate_with_retry(
                lambda: client.aio.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=contents,
                    config=config,
                )
            )
        await deduct_user_credits(user_id, 10, "1 Report Consumed")
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
        pdf.cell(0, 10, f"{type} {report_type} Report", ln=True, align="C")
        pdf.ln(10)

        pdf.set_font("NotoSans", "", 12)

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

        if pdf.get_y() > 260:
            pdf.add_page()

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

        filename = f"compatibility_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        s3_key = f"compatibility_reports/{filename}"

        s3_client.upload_fileobj(
            Fileobj=pdf_buffer,
            Bucket=S3_BUCKET,
            Key=s3_key,
            ExtraArgs={"ContentType": "application/pdf"},
        )

        file_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{s3_key}"
        saved_report = await save_compatibility_user_report(user_id, compatibility_doc["_id"], payload.profile_id, payload.is_comparison, file_url, report_text)

        chat_doc = {
            "report_id": saved_report.inserted_id,
            "user_id": ObjectId(user_id),
            "messages": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        return file_url


    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while generating compatibility report: {str(e)}"
        )
    


async def fetch_question_about_report(user_id, report_id, profile_id, payload, compatibility_report, language):
    try:
        user_oid = ObjectId(user_id)
        report_oid = ObjectId(report_id)

        if not profile_id:
            profile_id = user_id

        profile_oid = ObjectId(profile_id)

        conversation = await db.conversations.find_one({
            "report_id": report_oid,
            "user_id": user_oid,
            "profile_id": profile_oid,
            "category": "report"
        })

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        conversation_id = conversation["_id"]
        
        report = await db.user_reports.find_one({
            "report_id": report_oid,
            "user_id": user_oid,
            "profile_id": profile_oid,
        })

        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report Not Found"
            )

        report_text = report["report_text"]
        cursor = db.chat_history.find({
            "conversation_id": conversation_id,
            "user_id": user_oid,
            "profile_id": profile_oid
        }).sort("created_at", 1)

        previous_messages = await cursor.to_list(length=None)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an astrology assistant. "
                    "Answer the user's questions using ONLY the following report:\n\n"
                    f"{report_text}\n\n"
                    f"Respond in {language} language."
                )
            }
        ]

        MAX_HISTORY = 10
        for msg in previous_messages[-MAX_HISTORY:]:
            messages.append({
                "role": msg["role"],
                "content": msg["message"]
            })

        messages.append({
            "role": "user",
            "content": payload.user_question
        })

        async with llm_semaphore:
            response = await generate_with_retry(
                lambda: client.aio.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=[m["content"] for m in messages],
                    config=types.GenerateContentConfig(
                        temperature=1.0,
                )
            ))

        ai_reply = response.text

        await deduct_user_credits(user_id, 1, "1 Chat Consumed")

        now = datetime.utcnow()

        await db.chat_history.insert_many([
            {
                "conversation_id": conversation_id,
                "user_id": user_oid,
                "profile_id": profile_oid,
                "role": "user",
                "message": payload.user_question,
                "is_liked": False,
                "is_disliked": False,
                "created_at": now
            },
            {
                "conversation_id": conversation_id,
                "user_id": user_oid,
                "profile_id": profile_oid,
                "role": "assistant",
                "message": ai_reply,
                "is_liked": False,
                "is_disliked": False,
                "created_at": now
            }
        ])

        return ai_reply

    except HTTPException as http_err:
        raise http_err

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching query answer from AI: {str(e)}"
        )    


async def fetch_report_chat(user_id, report_id, profile_id, compatibility_report, language):
    try:
        query = {"report_id": ObjectId(report_id), "user_id": ObjectId(user_id)}
        if not profile_id:
            profile_id = user_id
        if compatibility_report:
            chat_collection = db.compatibility_report_chats
        else:
            chat_collection = db.conversations
            query["profile_id"] = ObjectId(profile_id)
        report_chat = await chat_collection.find_one(query)
        if not report_chat:
            report, conversation_id = await generate_report_from_ai(report_id, user_id, profile_id, False, language)
        else:
            conversation_id = report_chat["_id"]
        cursor = db.chat_history.find({"conversation_id": ObjectId(conversation_id), "user_id": ObjectId(user_id)})
        history = await cursor.to_list(length=None)
        return convert_mongo(history)
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching chat history for report: {str(e)}"
        )