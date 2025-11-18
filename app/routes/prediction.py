from fastapi import HTTPException, status, APIRouter, Depends, Query, Body
from app.deps.auth_deps import get_current_user
from app.models.prediction import PredictionCreate, PredictionUpdate
from app.utils.admin import is_user_admin
from app.services.prediction_service import add_prediction_to_db, fetch_predictions, fetch_prediction_by_id, update_prediction_by_id, delete_prediction_from_db
import json
from bson import json_util



router = APIRouter()

@router.post("/")
async def add_prediction(payload: PredictionCreate, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        await add_prediction_to_db(payload)
        return {"message": "Prediction Added Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding prediction: {str(e)}"
        )
    

@router.get("/")
async def get_reports(type: str = Query(None), current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to use this feature")
        
        reports = await fetch_predictions(type_filter=type)
        result_json = json.loads(json_util.dumps(reports))

        return {"message": "Predictions Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching predictions: {str(e)}"
        )


@router.get("/{id}")
async def get_prediction_by_id(id: str, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        prediction = await fetch_prediction_by_id(id)
        return {"message": "Prediction Fetched Successfully", "result": prediction}
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
    prediction_update: PredictionUpdate = Body(...),
    current_user = Depends(get_current_user)
):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=403, detail="You don't have access to this feature")

        update_data = prediction_update.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
        updated_report = await update_prediction_by_id(update_data, id)
        return {"message": "Prediction Updated Successfully", "result": updated_report}

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating report: {str(e)}"
        )
    

@router.delete("/{id}")
async def delete_prediction(id: str, current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        await delete_prediction_from_db(id)
        return {"message": "Prediction Deleted Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting prediction: {str(e)}"
        )

