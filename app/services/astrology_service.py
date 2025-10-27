from fastapi import HTTPException, status
from app.utils.helper import fetch_user_details, get_or_fetch_astrology_data, get_astrology_prediction


async def fetch_predictions_for_user(id, user_question):
    try:
        user_details = await fetch_user_details(id)
        astrology_data = await get_or_fetch_astrology_data(user_details["_id"], user_details)
        result = await get_astrology_prediction(astrology_data, user_question)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching predictions for user: {str(e)}"
        )