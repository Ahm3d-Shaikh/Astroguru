from fastapi import HTTPException, status, Body
from app.db.mongo import db
from bson import ObjectId



async def add_prediction_to_db(payload):
    try:
        await db.predictions.insert_one({
            "name": payload.name,
            "type": payload.type,
            "prompt": payload.prompt
        })
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding prediction to db: {str(e)}"
        )
    

async def fetch_predictions(type_filter=type):
    try:
        query = {}
        if type_filter:
            query["type"] = type_filter
        
        cursor = db.predictions.find(query)
        predictions = await cursor.to_list(length=None)

        if not predictions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Predictions Found")
        return predictions
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching predictions: {str(e)}"
        )
    

async def fetch_prediction_by_id(id):
    try:
        object_id = ObjectId(id)
        prediction = await db.predictions.find_one({"_id": object_id})

        if not prediction:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction Not Found")
        
        prediction["_id"] = str(prediction["_id"])
        return prediction
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching prediction by id: {str(e)}"
        )
    

async def update_prediction_by_id(update_data, id):
    try:
        object_id = ObjectId(id)
        result = await db.predictions.update_one({"_id": object_id}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")

        updated_prediction = await db.predictions.find_one({"_id": object_id})
        updated_prediction["_id"] = str(updated_prediction["_id"])
        return updated_prediction
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating prediction: {str(e)}"
        )
    

async def delete_prediction_from_db(id: str):
    try:
        object_id = ObjectId(id)
        await db.predictions.delete_one({"_id": object_id})
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting prediction from db: {str(e)}"
        )
