from fastapi import APIRouter, HTTPException, status, Depends, Body, Query
from app.deps.auth_deps import get_current_user
from app.models.report import ReportCreate, ReportUpdate
from app.utils.admin import is_user_admin
from app.services.report_service import add_report_in_db, fetch_reports, fetch_report_by_id, update_report_by_id, delete_report_from_db, add_user_report_to_db, fetch_user_reports
import json
from bson import json_util


router = APIRouter()

@router.post("/")
async def add_report(payload:ReportCreate, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        await add_report_in_db(payload)
        return {"message": "Report Added Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding report: {str(e)}"
        )
    

@router.get("/")
async def get_reports(category: str = Query(None), current_user = Depends(get_current_user)):
    try:
        reports = await fetch_reports(category)
        result_json = json.loads(json_util.dumps(reports))
        return {"message": "Reports Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching reports: {str(e)}"
        )
    

@router.post("/user/{id}")
async def add_user_report(id: str, current_user = Depends(get_current_user)):
    try:
        if not id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report ID Is Required")
        user_id = current_user["_id"]
        await add_user_report_to_db(id, user_id)
        return {"message": "User Report Added Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding user report: {str(e)}"
        )
    

@router.get("/user")
async def get_user_reports(current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        reports = await fetch_user_reports(user_id)
        result_json = json.loads(json_util.dumps(reports))
        return {"message": "User Reports Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while getting user reports: {str(e)}"
        )

@router.get("/{id}")
async def get_report_by_id(id: str, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        report = await fetch_report_by_id(id)
        return {"message": "Report Fetched Successfully", "result": report}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching report by id: {str(e)}"
        )
    

@router.patch("/{id}")
async def patch_report_by_id(
    id: str,
    report_update: ReportUpdate = Body(...),
    current_user = Depends(get_current_user)
):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=403, detail="You don't have access to this feature")

        update_data = report_update.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
        updated_report = await update_report_by_id(update_data, id)
        return {"message": "Report updated successfully", "result": updated_report}

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating report: {str(e)}"
        )
    

@router.delete("/{id}")
async def delete_report(id: str, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        await delete_report_from_db(id)
        return {"message": "Report Deleted Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting report: {str(e)}"
        )

