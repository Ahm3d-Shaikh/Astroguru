from fastapi import APIRouter, HTTPException, status, Body, Depends
from app.deps.auth_deps import get_current_user
from app.models.profile import UserProfileCreate, UserProfileUpdate
from app.services.profile_service import add_profile_to_db, get_profiles_for_user, get_specific_profile_from_db, delete_user_profile_from_db, edit_profile_in_db
import json
from bson import json_util

router = APIRouter()


@router.post("/")
async def create_profile(payload: UserProfileCreate, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        await add_profile_to_db(payload, user_id)
        return {"message": "User Profile Added Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while creating user profile: {str(e)}"
        )
    

@router.get("/")
async def get_profiles(current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        profiles = await get_profiles_for_user(user_id)
        result_json = json.loads(json_util.dumps(profiles))
        return {"message": "Profiles Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user profiles: {str(e)}"
        )
    

@router.get("/{id}")
async def get_profile_by_id(id: str, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        profile = await get_specific_profile_from_db(id, user_id)
        return {"message": "Profile Fetched Successfully", "result": profile}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching profile by id: {str(e)}"
        )
    

@router.delete("/{id}")
async def delete_profile(id: str, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        await delete_user_profile_from_db(id, user_id)
        return {"message": "User Profile Deleted Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting profile: {str(e)}"
        )
    

@router.patch("/{id}")
async def edit_profile(id: str, payload: UserProfileUpdate, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        update_data = payload.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
        updated_prompt = await edit_profile_in_db(id, user_id, update_data)
        return {"message": "Profile Updated Successfully", "result": updated_prompt}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while editing prompt: {str(e)}"
        )