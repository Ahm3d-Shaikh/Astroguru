from fastapi import HTTPException, APIRouter, status, Depends
from app.models.prompt import PromptCreate, PromptUpdate
from app.services.prompt_service import add_system_prompt_to_db, fetch_system_prompts, edit_prompt_in_db
from app.deps.auth_deps import get_current_user
from app.utils.enums.category import Category
from bson import json_util
import json
from app.utils.admin import is_user_admin
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
        
        await add_system_prompt_to_db(payload.category, payload.prompt)
        return {"message": "Prompt Added Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding system prompt: {str(e)}"
        )
    

@router.patch("/{id}")
async def edit_prompt(id: str, payload: PromptUpdate, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        update_data = payload.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
        updated_prompt = await edit_prompt_in_db(id, update_data)
        return {"message": "Prompt Updated Successfully", "result": updated_prompt}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while editing prompt: {str(e)}"
        )