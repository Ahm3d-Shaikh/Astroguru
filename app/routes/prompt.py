from fastapi import HTTPException, APIRouter, status, Depends
from app.models.prompt import PromptCreate
from app.services.prompt_service import add_system_prompt_to_db, fetch_system_prompts
from app.deps.auth_deps import get_current_user
from app.utils.enums.category import Category
from bson import json_util
import json
router = APIRouter()


@router.get("/")
async def get_system_prompt(current_user = Depends(get_current_user)):
    try:
        role = current_user["role"]
        if role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        prompts = await fetch_system_prompts()
        result_json = json.loads(json_util.dumps(prompts))
        return {"message": "Prompts Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching system prompts: {str(e)}"
        )


@router.post("/")
async def add_system_prompt(payload: PromptCreate, current_user =Depends(get_current_user)):
    try: 
        role = current_user["role"]
        if role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        if payload.category not in Category:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Prompt Category")
        
        await add_system_prompt_to_db(payload.category, payload.prompt)
        return {"message": "Prompt Added Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding system prompt: {str(e)}"
        )