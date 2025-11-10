from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId



async def add_report_in_db(payload):
    try:
        await db.reports.insert_one({
            "name": payload.name,
            "type": payload.type,
            "sub_title": payload.sub_title,
            "description": payload.description,
            "prompt": payload.prompt
        })
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding report in db: {str(e)}"
        )
    

async def fetch_reports(type_filter: str = None):
    try:
        query = {}
        if type_filter:
            query["type"] = type_filter
        
        cursor = db.reports.find(query)
        reports = await cursor.to_list(length=None)

        if not reports:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Reports Found")
        return reports
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching reports: {str(e)}"
        )
    

async def fetch_report_by_id(id):
    try:
        object_id = ObjectId(id)
        report = await db.reports.find_one({"_id": object_id})

        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report Not Found")
        
        report["_id"] = str(report["_id"])
        return report
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching report by id: {str(e)}"
        )
    

async def update_report_by_id(update_data, id):
    try:
        object_id = ObjectId(id)
        result = await db.reports.update_one({"_id": object_id}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

        updated_report = await db.reports.find_one({"_id": object_id})
        updated_report["_id"] = str(updated_report["_id"])
        return updated_report
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating report: {str(e)}"
        )