from fastapi import APIRouter, HTTPException, Depends, status, Body, Query
from app.services.astrology_service import fetch_predictions_for_user, fetch_chat_history_for_user
from app.models.user_question import UserQuestionObj
from app.deps.auth_deps import get_current_user
from app.utils.enums.category import Category
import json
from bson import json_util

router = APIRouter()

@router.post("/future_prediction")
async def fetch_astrology_details(user_question_object: UserQuestionObj, user = Depends(get_current_user)):
    try:
        user_id = user["_id"]
        result, category = await fetch_predictions_for_user(user_id, user_question_object.user_question)
        return {"message": "Prediction Fetched Successfully", "result": result, "category": category}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )
    

@router.get("/chat-history")
async def get_chat_history(category: str = Query(None), current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        chat_history = await fetch_chat_history_for_user(category, user_id)
        result_json = json.loads(json_util.dumps(chat_history))
        return {"message": "Chat History Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching chat history: {str(e)}"
        )