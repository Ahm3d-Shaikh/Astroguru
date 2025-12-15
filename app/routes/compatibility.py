from fastapi import HTTPException, APIRouter, Body, status, Depends, Query
from app.deps.auth_deps import get_current_user
from app.utils.admin import is_user_admin
import json
from bson import json_util
from app.services.compatibility_service import add_compatibility_prompt, fetch_compatibilities, delete_compatibility_from_db, update_compatibility_by_id, fetch_compatibility_by_id, generate_compatibility_report
from app.models.compatibility import CompatibilityCreate, CompatibilityUpdate, CompatibilityReportCreate

router = APIRouter()


@router.post("/")
async def add_compatibility(payload: CompatibilityCreate, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to use this feature")
        
        await add_compatibility_prompt(payload)
        return {"message": "Compatibility Added Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding compatibility: {str(e)}"
        )
    

@router.post("/report")
async def get_compatibility_between_profiles(payload: CompatibilityReportCreate, pdf_report: bool = Query(None), current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        result = await generate_compatibility_report(user_id, payload, pdf_report)
        return {"message": "Compatibility Report Fetched Successfully", "result": result}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while generating compatibility report: {str(e)}"
        )

@router.get("/")
async def get_compatibilities(is_comparison: bool = Query(False), current_user = Depends(get_current_user)):
    try:
        compatibilities = await fetch_compatibilities(is_comparison)
        result_json = json.loads(json_util.dumps(compatibilities))
        return {"message": "Compatibilities Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching compatibilities: {str(e)}"
        )
    

@router.delete("/{id}")
async def delete_compatibility(id: str, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to use this feature")
        
        await delete_compatibility_from_db(id)
        return {"message": "Compatibility Deleted Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting compatibility: {str(e)}"
        )
    


@router.get("/{id}")
async def get_compatibility_by_id(id: str, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        compatibility = await fetch_compatibility_by_id(id)
        return {"message": "Compatibility Fetched Successfully", "result": compatibility}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching prediction by id: {str(e)}"
        )


@router.patch("/{id}")
async def patch_report_by_id(
    id: str,
    payload: CompatibilityUpdate = Body(...),
    current_user = Depends(get_current_user)
):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=403, detail="You don't have access to this feature")

        update_data = payload.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
        updated_compatibility = await update_compatibility_by_id(update_data, id)
        return {"message": "Compatibility Updated Successfully", "result": updated_compatibility}

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating report: {str(e)}"
        )
