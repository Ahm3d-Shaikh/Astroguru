from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId
from google.genai import types
from datetime import datetime
import json
import re
from app.clients.gemini_client import client
from app.utils.mongo import convert_mongo
from app.services.conversation_service import fetch_conversations
from app.utils.helper import fetch_user_details, get_or_fetch_astrology_data, get_astrology_prediction, fetch_user_report, generate_report_helper, generate_predictions_for_homepage, fetch_profile_details


async def fetch_predictions_for_user(id, profile_id, user_question, conversation_id, language):
    try:
        # If profile_id == user_id → use users table
        if profile_id == id:
            profile_details = await fetch_user_details(id)
        else:
            profile_details = await fetch_profile_details(id, profile_id)
        astrology_data = await get_or_fetch_astrology_data(id, profile_id, profile_details)
        result, category, conversation_id = await get_astrology_prediction(astrology_data, user_question, id, profile_id, conversation_id, language)
        return result, category, conversation_id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching predictions for user: {str(e)}"
        )
    

async def fetch_chat_history_for_user(category, id, user_id):
    try:
        query = {
            "user_id": ObjectId(user_id),
            "conversation_id": ObjectId(id)
        }
        if category:
            query["category"] = category

        cursor = db.chat_history.find(query).sort("created_at", 1)
        chat_history = await cursor.to_list(length=None)

        if not chat_history:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Chat History Found For The User")
        
        return chat_history
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching chat history from db: {str(e)}"
        )
    

async def generate_report_from_ai(id, user_id, profile_id, pdf_report, language):
    user_report = await fetch_user_report(id, user_id, profile_id)
    if not user_report:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    
    # If profile_id == user_id → use users table
    if profile_id == user_id:
        profile_details = await fetch_user_details(user_id)
    else:
        profile_details = await fetch_profile_details(user_id, profile_id)
    astrology_data = await get_or_fetch_astrology_data(user_id, profile_id, profile_details)
    generated_report = await generate_report_helper(profile_details, astrology_data, user_report, pdf_report, user_id, profile_id, language)
    return generated_report


async def fetch_dashboard_predictions(user_id, profile_id, language):
    # If profile_id == user_id → use users table
    if profile_id == user_id:
        profile_details = await fetch_user_details(user_id)
    else:
        profile_details = await fetch_profile_details(user_id, profile_id)
    astrology_data = await get_or_fetch_astrology_data(user_id, profile_id, profile_details)
    text_output, prediction_dict = await generate_predictions_for_homepage(profile_details, astrology_data, language)
    return text_output, prediction_dict


async def fetch_dynamic_questions(user_id, language):
    try:
        last_conversation = await db.conversations.find_one({"user_id": ObjectId(user_id)}, sort=[("created_at", -1)])

        if not last_conversation:
            return [
                "What does my zodiac sign say about today?",
                "How's my love life looking this month?",
                "Will I see career growth this year?",
                "Any challenges coming in my Kundali soon?"
            ]
        
        last_three_questions = await db.chat_history.find(
            {
                "conversation_id": last_conversation["_id"],
                "role": "user"  
            },
            sort=[("created_at", -1)]
        ).limit(3).to_list(length=3)

        last_three_questions.reverse()

        questions_text = "\n".join(
            [f"{i+1}. {q['message']}" for i, q in enumerate(last_three_questions)]
        )
        dynamic_prompt = f"""
            The user previously asked:

            {questions_text}

            Generate 3 new astrology follow-up questions.

            The questions must sound like the user is asking the AI about their own life.
            Do NOT frame the questions as if AI is asking the user (avoid "Do you", "Are you", "Have you").

            Keep each question short and precise (15 to 20 words max).
            Respond in {language} language.
            Return response strictly in JSON format.

            {{
            "questions": [
                "question 1",
                "question 2",
                "question 3"
            ]
            }}
            """


        config = types.GenerateContentConfig(
        temperature=0.8, 
        max_output_tokens=300
        )

        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=dynamic_prompt,
            config=config,
        )

        raw_text = response.text.strip()
        cleaned_text = re.sub(r"```json|```", "", raw_text).strip()
        parsed = json.loads(cleaned_text)
        suggested_questions = parsed["questions"]
        return suggested_questions
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching questions: {str(e)}"
        )



async def add_chat_like_in_db(user_id, payload, profile_id=None):
    try:
        filter_query = {
            "_id": ObjectId(payload.chat_id),
            "user_id": ObjectId(user_id),
            "conversation_id": ObjectId(payload.conversation_id)
        }

        if profile_id:
            filter_query["profile_id"] = ObjectId(profile_id)

        result = await db.chat_history.update_one(
            filter_query,
            {
                "$set": {
                    "is_liked": True,
                    "is_disliked": False
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat Not Found Or Already Updated"
            )

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding chat like in db: {str(e)}"
        )    

async def add_chat_dislike_in_db(user_id, payload, profile_id=None):
    try:
        filter_query = {
            "_id": ObjectId(payload.chat_id),
            "user_id": ObjectId(user_id),
            "conversation_id": ObjectId(payload.conversation_id)
        }

        if profile_id:
            filter_query["profile_id"] = ObjectId(profile_id)

        result = await db.chat_history.update_one(
            filter_query,
            {
                "$set": {
                    "is_disliked": True,
                    "is_liked": False
                }
            }
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat Not Found Or Already Updated"
            )
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding chat dislike in db: {str(e)}"
        )
    

async def fetch_user_likes(id, profile_id):
    try:
        cursor = db.chat_history.find({"user_id": ObjectId(id), "profile_id": ObjectId(profile_id), "is_liked": True})
        likes = await cursor.to_list(length=None)
        if not likes:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Likes Not Found")
        
        return convert_mongo(likes)
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user likes: {str(e)}"
        )
    

async def fetch_user_dislikes(id, profile_id):
    try:
        cursor = db.chat_history.find({"user_id": ObjectId(id), "profile_id": ObjectId(profile_id), "is_disliked": True})
        dislikes = await cursor.to_list(length=None)
        if not dislikes:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dislikes Not Found")
        
        return convert_mongo(dislikes)
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user likes: {str(e)}"
        )
    


async def fetch_user_profile_summary(profile_details, conversations, reports):
    try:
        system_prompt = """
        Generate a user profile summary based on the user details and the conversations which the user had with the AI chat.
        Example Response:

        User Name: Riya Sharma
        User ID: AST-10245
        Basic Details

        DOB: 14 Aug 1996
        Time of Birth: 03:42 AM
        Place of Birth: Jaipur, India
        Account Created: 12 Jan 2026
        Last Active: 24 Feb 2026
        
        Key Facts from AI Chats (Auto-Extracted)

        Recently changed job (Sep 2025)
        Breakup in Nov 2025
        Planning to move abroad
        Frequently worried about career growth
        Often asks about marriage timing
        Usage Insights

        Most discussed topic: Career
        Active hours: Late night
        Reports viewed: 8

        """
        contents = [
        f"Conversations: \n{conversations}\n\n"
        f"Here's the details of the user: \n{profile_details}\n\n"
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
        return reply
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user profile summary: {str(e)}"
        )