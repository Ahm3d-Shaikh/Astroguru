from fastapi import HTTPException, status
from app.db.mongo import db
from app.utils.helper import fetch_user_details, get_or_fetch_astrology_data, get_astrology_prediction, fetch_user_report, generate_report_helper, generate_predictions_for_homepage


async def fetch_predictions_for_user(id, user_question):
    try:
        user_details = await fetch_user_details(id)
        astrology_data = await get_or_fetch_astrology_data(user_details["_id"], user_details)
        result, category = await get_astrology_prediction(astrology_data, user_question, id)
        return result, category
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching predictions for user: {str(e)}"
        )
    

async def fetch_chat_history_for_user(category, user_id):
    try:
        query = {}
        if category:
            query["category"] = category

        cursor = db.chat_history.find(query)
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
    

async def generate_report_from_ai(id, user_id, pdf_report):
    user_report = await fetch_user_report(id, user_id)
    if not user_report:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    
    user_details = await fetch_user_details(user_id)
    astrology_data = await get_or_fetch_astrology_data(user_details["_id"], user_details)
    generated_report = await generate_report_helper(user_details, astrology_data, user_report, pdf_report)
    return generated_report


async def fetch_dashboard_predictions(user_id):
    user_details = await fetch_user_details(user_id)
    astrology_data = await get_or_fetch_astrology_data(user_details["_id"], user_details)
    text_output, prediction_dict = await generate_predictions_for_homepage(user_details, astrology_data)
    return text_output, prediction_dict
