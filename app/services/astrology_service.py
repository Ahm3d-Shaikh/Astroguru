from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId
from app.utils.helper import fetch_user_details, get_or_fetch_astrology_data, get_astrology_prediction, fetch_user_report, generate_report_helper, generate_predictions_for_homepage, fetch_profile_details


async def fetch_predictions_for_user(id, profile_id, user_question, conversation_id):
    try:
        # If profile_id == user_id → use users table
        if profile_id == id:
            profile_details = await fetch_user_details(id)
        else:
            profile_details = await fetch_profile_details(id, profile_id)
        astrology_data = await get_or_fetch_astrology_data(id, profile_id, profile_details)
        result, category, conversation_id = await get_astrology_prediction(astrology_data, user_question, id, profile_id, conversation_id)
        return result, category, conversation_id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching predictions for user: {str(e)}"
        )
    

async def fetch_chat_history_for_user(category, id, user_id, profile_id):
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
    

async def generate_report_from_ai(id, user_id, profile_id, pdf_report):
    user_report = await fetch_user_report(id, user_id, profile_id)
    if not user_report:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    
    # If profile_id == user_id → use users table
    if profile_id == user_id:
        profile_details = await fetch_user_details(user_id)
    else:
        profile_details = await fetch_profile_details(user_id, profile_id)
    astrology_data = await get_or_fetch_astrology_data(user_id, profile_id, profile_details)
    generated_report = await generate_report_helper(profile_details, astrology_data, user_report, pdf_report)
    return generated_report


async def fetch_dashboard_predictions(user_id, profile_id):
    # If profile_id == user_id → use users table
    if profile_id == user_id:
        profile_details = await fetch_user_details(user_id)
    else:
        profile_details = await fetch_profile_details(user_id, profile_id)
    astrology_data = await get_or_fetch_astrology_data(user_id, profile_id, profile_details)
    text_output, prediction_dict = await generate_predictions_for_homepage(profile_details, astrology_data)
    return text_output, prediction_dict
