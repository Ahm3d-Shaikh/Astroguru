from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId
from app.utils.mongo import convert_mongo
from app.services.subscription_service import deduct_user_credits



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
    

async def fetch_reports(category: str = None):
    try:
        query = {}
        if category:
            query["type"] = category
        
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
    
async def fetch_remaining_reports(user_id, profile_id=None):
    try:
        query = {
            "user_id": ObjectId(user_id)
        }

        if profile_id:
            query["profile_id"] = ObjectId(profile_id)
        
        downloaded_reports_cursor = db.user_reports.find(query)
        downloaded_reports = await downloaded_reports_cursor.to_list(length=None)
        downloaded_ids = [r["report_id"] for r in downloaded_reports]

        remaining_reports_cursor = db.reports.find(
            {"_id": {"$nin": downloaded_ids}}
        )
        remaining_reports = await remaining_reports_cursor.to_list(length=None)

        return convert_mongo(remaining_reports)
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching remaining reports from db: {str(e)}"
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
    

async def delete_report_from_db(id: str):
    try:
        object_id = ObjectId(id)
        await db.reports.delete_one({"_id": object_id})
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting report from db: {str(e)}"
        )
    

async def add_user_report_to_db(id, user_id, profile_id):
    try:
        existing_report = await db.user_reports.find_one({
            "user_id": ObjectId(user_id),
            "report_id": ObjectId(id),
            "profile_id": ObjectId(profile_id)
        })

        if existing_report:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already purchased this report")
        
        await db.user_reports.insert_one({
            "user_id": ObjectId(user_id),
            "profile_id": ObjectId(profile_id),
            "report_id": ObjectId(id),
            "file_url": None,
            "report_text": None
        })
        await deduct_user_credits(user_id, 10, "1 Report Consumed")
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding user report to db: {str(e)}"
        )


async def fetch_user_reports_for_admin(user_id, profile_id=None):
    try:
        match_query = {
            "user_id": ObjectId(user_id)
        }
        if profile_id:
            match_query["profile_id"] = ObjectId(profile_id)

        pipeline = [
            {"$match": match_query},
            {
                "$lookup": {
                    "from": "reports",           
                    "localField": "report_id",   
                    "foreignField": "_id",       
                    "as": "report_info"          
                }
            },
            {
                "$unwind": {
                    "path": "$report_info",
                    "preserveNullAndEmptyArrays": True  
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "user_id": 1,
                    "profile_id": 1,
                    "report_id": 1,
                    "file_url": 1,
                    "report_text": 1,            
                    "report_name": "$report_info.name"  
                }
            }
        ]

        user_reports = await db.user_reports.aggregate(pipeline).to_list(length=None)

        if len(user_reports) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No Downloaded Reports Found For The User"
            )

        return user_reports
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user reports: {str(e)}"
        )

async def fetch_user_reports(user_id, profile_id=None):
    try:
        query = {
            "user_id": ObjectId(user_id)
        }

        if profile_id:
            query["profile_id"] = ObjectId(profile_id)

        user_reports = await db.user_reports.find(query).to_list(length=None)

        if len(user_reports) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No Downloaded Reports Found For The User"
            )

        report_ids = [ur["report_id"] for ur in user_reports]

        reports = await db.reports.find(
            {"_id": {"$in": report_ids}}
        ).to_list(length=None)

        return reports

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user reports: {str(e)}"
        )
