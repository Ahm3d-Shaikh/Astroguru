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
    

@router.post("/report/{id}")
async def generate_report(id: str, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        if not id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report ID Is Required")
        
        generated_report = await generate_report_from_ai(id, user_id)
        return {"message": "Report Generated Successfully", "result": generated_report}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while generating report: {str(e)}"
        )
    

@router.post("/dashboard")
async def get_dashboard_prediction(current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        text_output, prediction_dict = await fetch_dashboard_predictions(user_id)
        return {"message": "Predictions Fetched Successfully", "text": text_output, "predictions": prediction_dict}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while getting dashboard prediction: {str(e)}"
        )