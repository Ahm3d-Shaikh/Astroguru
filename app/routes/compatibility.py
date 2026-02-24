from fastapi import HTTPException, APIRouter, Body, status, Depends, Query
from app.deps.auth_deps import get_current_user
from app.utils.admin import is_user_admin
import json
from bson import json_util
from app.services.compatibility_service import add_compatibility_prompt, fetch_compatibilities, delete_compatibility_from_db, update_compatibility_by_id, fetch_compatibility_by_id, generate_compatibility_report, fetch_user_compatibility_reports, fetch_question_about_report, fetch_report_chat
from app.models.compatibility import CompatibilityCreate, CompatibilityUpdate, CompatibilityReportCreate
from app.models.user_question import ChatQuestionPayload

router = APIRouter()


@router.post("/")
async def add_compatibility(payload: CompatibilityCreate, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to use this feature")
        type = "Compatibility" if payload.is_comparison is False else "Comparison"
        await add_compatibility_prompt(payload)
        return {"message": f"{type} Added Successfully"}
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
        type = "Compatibility" if payload.is_comparison is False else "Comparison"
        result = await generate_compatibility_report(user_id, payload, pdf_report, type)
        return {"message": f"{type} Report Fetched Successfully", "result": result}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while generating compatibility report: {str(e)}"
        )

@router.post("/report/{report_id}/chat")
async def ask_question_about_report(report_id: str, payload: ChatQuestionPayload, compatibility_report: str = Query(None),  profile_id: str = Query(None), current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        if not report_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report ID Is Required")
        answer = await fetch_question_about_report(user_id, report_id, profile_id, payload, compatibility_report)
        return {"message": "Query Answered Successfully", "result": answer}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while generating report query: {str(e)}"
        )    

@router.get("/report/{report_id}/chat")
async def get_report_chat(report_id: str, compatibility_report: str = Query(None), profile_id: str = Query(None), current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        if not report_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report ID Is Required")
        chat_history = await fetch_report_chat(user_id, report_id, profile_id, compatibility_report)
        return {"message": "Query Answered Successfully", "result": chat_history}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while generating report query: {str(e)}"
        )    


@router.get("/report")
async def get_user_compatibility_reports(is_comparison: bool = Query(False), current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        user_reports = await fetch_user_compatibility_reports(user_id, is_comparison)
        result_json = json.loads(json_util.dumps(user_reports))
        return {"message": "User Reports Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user compatibility reports: {str(e)}"
        )

@router.get("/")
async def get_compatibilities(current_user = Depends(get_current_user)):
    try:
        compatibilities = await fetch_compatibilities()
        result_json = json.loads(json_util.dumps(compatibilities))
        return {"message": "Reports Fetched Successfully", "result": result_json}
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
