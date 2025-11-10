from fastapi import APIRouter, HTTPException, status, Depends, Body
from app.deps.auth_deps import get_current_user
from app.models.report import ReportCreate, ReportUpdate
from app.utils.admin import is_user_admin
from app.services.report_service import add_report_in_db, fetch_reports, fetch_report_by_id, update_report_by_id
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
async def get_reports(current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to use this feature")
        
        reports = await fetch_reports()
        result_json = json.loads(json_util.dumps(reports))

        return {"message": "Reports Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching reports: {str(e)}"
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
