from fastapi import HTTPException, APIRouter, status, Depends, Body, Query
from app.deps.auth_deps import get_current_user
from app.utils.admin import is_user_admin
from app.services.user_service import fetch_users, fetch_user_by_id, delete_user_by_id, fetch_logged_in_user_details, edit_user_details, fetch_dashboard_details_for_user, delete_logged_in_user_by_id
from app.utils.helper import fetch_chart_image
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
async def get_dashboard_details_for_user(id: str, profile_id: str = Query(None), current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        if profile_id is None:
            profile_id = id
        result = await fetch_dashboard_details_for_user(id, profile_id)
        return {"message": "User Details Fetched Successfully", "result": result}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching dashboard user details: {str(e)}"
        )
    
@router.post("/user-details/chart-image/{id}")
async def get_chart_image(id: str, chart: str = Query(), profile_id: str = Query(None), current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
    
        if not chart:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chart Is Required")
        
        if profile_id is None:
            profile_id = id
        chart_image = await fetch_chart_image(id, chart, profile_id)
        return {"message": "Chart Image Fetched Successfully", "result": chart_image}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching chart image: {str(e)}"
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
    

@router.delete("/")
async def delete_logged_in_user(current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        await delete_logged_in_user_by_id(user_id)
        return {"message": "User Deleted Successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting user: {str(e)}"
        )