from fastapi import APIRouter, HTTPException, Depends, status, Body
from app.services.astrology_service import fetch_predictions_for_user
from app.models.user_question import UserQuestionObj
from app.deps.auth_deps import get_current_user
from app.utils.enums.category import Category

router = APIRouter()

@router.post("/future_prediction")
async def fetch_astrology_details(user_question_object: UserQuestionObj, user = Depends(get_current_user)):
    try:
        user_id = user["_id"]
        if user_question_object.category not in Category:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Prompt Category")
        
        result = await fetch_predictions_for_user(user_id, user_question_object.user_question, user_question_object.category)
        return {"message": "Prediction Fetched Successfully", "result": result}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )