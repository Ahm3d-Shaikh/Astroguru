from fastapi import HTTPException, status, Body
from app.db.mongo import db
from bson import ObjectId
from datetime import datetime
from app.utils.helper import fetch_profile_details, get_or_fetch_astrology_data, markdown_to_plain, get_zodiac_sign
from app.clients.gemini_client import client
from google.genai import types
from fpdf import FPDF
import io
import re
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


async def fetch_user_compatibility_reports(user_id, is_comparison):
    try:
        pipeline = [
            {"$match": {"user_id": ObjectId(user_id), "is_comparison": is_comparison}},
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

async def save_compatibility_user_report(user_id, compatibility_id, profile_id, is_comparison, file_url):
    profile_ids = [ObjectId(pid) if isinstance(pid, str) else pid for pid in profile_id]

    cursor = db.user_compatibility_reports.find({
        "user_id": ObjectId(user_id),
        "compatibility_id": ObjectId(compatibility_id),
        "pdf_report": {"$ne": None} 
    })
    existing_docs = await cursor.to_list(length=None)
    if not existing_docs:
        await db.user_compatibility_reports.insert_one({
            "user_id": ObjectId(user_id),
            "profile_id": profile_ids,
            "compatibility_id": ObjectId(compatibility_id),
            "is_comparison": is_comparison,
            "pdf_report": file_url,  
            "created_at": datetime.utcnow()
        })

async def generate_compatibility_report(user_id, payload, pdf_report, report_type):
    try:
        profiles = dict()
        type = payload.type
        for profile in payload.profile_id:
            profile_details = await fetch_profile_details(user_id, profile)
            astrology_data = await get_or_fetch_astrology_data(user_id, profile, profile_details)
            astrology_summary = "\n".join(f"{key}: {value}" for key, value in astrology_data.items())
            profiles[profile] = {
                "profile_details": profile_details,
                "astrology_summary": astrology_summary
            }

        compatibility_doc = await db.compatibilities.find_one({"type": type, "is_comparison": payload.is_comparison})
        if not compatibility_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{report_type} Not Found")
        prompt = compatibility_doc["prompt"]

        contents = [
            f"Profiles:\n\n {profiles}",
            f"Use the profile details and astrological details to generate a detailed, warm, human-sounding {report_type} report."
        ]

        config = types.GenerateContentConfig(
        temperature = 0.2,
        max_output_tokens = 2000,
        system_instruction = prompt
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

        filename = f"compatibility_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        s3_key = f"compatibility_reports/{filename}"

        s3_client.upload_fileobj(
            Fileobj=pdf_buffer,
            Bucket=S3_BUCKET,
            Key=s3_key,
            ExtraArgs={"ContentType": "application/pdf"},
        )

        file_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{s3_key}"
        await save_compatibility_user_report(user_id, compatibility_doc["_id"], payload.profile_id, payload.is_comparison, file_url)
        return file_url


    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while generating compatibility report: {str(e)}"
        )