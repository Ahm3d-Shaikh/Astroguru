from fastapi import HTTPException, APIRouter, status, Depends, Body, Query
from app.deps.auth_deps import get_current_user
from app.utils.admin import is_user_admin
from app.services.user_service import fetch_users, fetch_user_by_id, delete_user_by_id, fetch_logged_in_user_details, edit_user_details, fetch_dashboard_details_for_user
import json
from bson import json_util
from app.models.user import UserUpdate


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
    

@router.get("/user-details")
async def get_user_details(current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        details = await fetch_logged_in_user_details(user_id)
        return {"message": "User Details Fetched Successfully", "result": details}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user details: {str(e)}"
        )

@router.get("/user-details/{id}")
async def get_dashboard_details_for_user(id: str, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        result = await fetch_dashboard_details_for_user(id)
        return {"message": "User Details Fetched Successfully", "result": result}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching dashboard user details: {str(e)}"
        )

@router.get("/{id}")
async def get_user_by_id(id: str, current_user = Depends(get_current_user)):
    try:
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
    
@router.patch("/")
async def edit_logged_in_user(payload: UserUpdate, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        update_data = payload.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
        updated_user = await edit_user_details(user_id, update_data)
        return {"message": "User Details Updated Successfully", "result": updated_user}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while editing user details: {str(e)}"
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