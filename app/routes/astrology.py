from fastapi import APIRouter, HTTPException, Depends, status, Body, Query
from app.services.astrology_service import fetch_predictions_for_user, fetch_chat_history_for_user, generate_report_from_ai, fetch_dashboard_predictions
from app.models.user_question import UserQuestionObj
from app.deps.auth_deps import get_current_user
from app.utils.enums.category import Category
import json
from bson import json_util
from fastapi.responses import FileResponse

router = APIRouter()

@router.post("/future_prediction")
async def fetch_astrology_details(user_question_object: UserQuestionObj, profile_id: str = Query(None), user = Depends(get_current_user)):
    try:
        user_id = user["_id"]
        if profile_id is None:
            profile_id = user_id
        conversation_id = user_question_object.conversation_id
        result, category, new_conversation_id = await fetch_predictions_for_user(user_id, profile_id, user_question_object.user_question, conversation_id)
        return {"message": "Prediction Fetched Successfully", "result": result, "category": category, "conversation_id": new_conversation_id}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )
    

@router.get("/chat-history/{id}")
async def get_chat_history(id: str, category: str = Query(None), current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        chat_history = await fetch_chat_history_for_user(category, id, user_id)
        result_json = json.loads(json_util.dumps(chat_history))
        return {"message": "Chat History Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching chat history: {str(e)}"
        )
    

@router.post("/report/{id}")
async def generate_report(id: str, profile_id: str = Query(None), pdf_report: bool = Query(None), current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        if not id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report ID Is Required")
        if profile_id is None:
            profile_id = user_id
        generated_report = await generate_report_from_ai(id, user_id, profile_id, pdf_report)
        return {"message": "Report Generated Successfully", "result": generated_report}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while generating report: {str(e)}"
        )
    

@router.post("/dashboard")
async def get_dashboard_prediction(profile_id: str = Query(None), current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        if profile_id is None:
            profile_id = user_id
        text_output, prediction_dict = await fetch_dashboard_predictions(user_id, profile_id)
        return {"message": "Predictions Fetched Successfully", "text": text_output, "predictions": prediction_dict}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while getting dashboard prediction: {str(e)}"
        )