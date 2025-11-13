from fastapi import HTTPException, APIRouter, status, Depends, Body, Query
from app.deps.auth_deps import get_current_user
from app.utils.admin import is_user_admin
from app.services.user_service import fetch_users, fetch_user_by_id, delete_user_by_id
import json
from bson import json_util


router = APIRouter()


@router.get("/")
async def get_users(type: str = Query(None), current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        users = await fetch_users(type_filter=type)
        result_json = json.loads(json_util.dumps(users))
        return {"message": "Users Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching users: {str(e)}"
        )
    

@router.get("/{id}")
async def get_user_by_id(id: str, current_user = Depends(get_current_user)):
    try:
        print(id)
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        user = await fetch_user_by_id(id)
        return {"message": "User Fetched Successfully", "result": user}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user by id: {str(e)}"
        )
    

@router.delete("/{id}")
async def delete_user(id: str, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        await delete_user_by_id(id)
        return {"message": "User Deleted Successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting user: {str(e)}"
        )