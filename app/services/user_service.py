from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId

async def fetch_users(type_filter: str = None):
    try:
        query = {}
        if type_filter:
            query["role"] = type_filter
        cursor = db.users.find(query)
        users = await cursor.to_list(length=None)

        if not users:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Users Found")
        
        return users
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching users: {str(e)}"
        )
    

async def fetch_user_by_id(id):
    try:
        user = await db.users.find_one({"_id": ObjectId(id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Not Found")
        
        user["_id"] = str(user["_id"])
        return user
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user by id: {str(e)}"
        )
    

async def delete_user_by_id(id):
    try:
        await db.users.delete_one({"_id": ObjectId(id)})
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting user: {str(e)}"
        )
