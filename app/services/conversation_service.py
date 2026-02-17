from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId

async def fetch_conversations(user_id, profile_id=None, search_term = None):
    try:
        query = {
            "user_id": ObjectId(user_id) 
        }

        if profile_id:
            query["profile_id"] = ObjectId(profile_id)
        
        if search_term:
            query["title"] = {"$regex": search_term, "$options": "i"}
            
        cursor = db.conversations.find(query)
        conversations = await cursor.to_list(length=None)
        if len(conversations) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Conversations Found")
        return conversations
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching conversations from db: {str(e)}"
        )
    

async def edit_conversation_in_db(id, user_id, update_data):
    try:
        result = await db.conversations.update_one({"_id": ObjectId(id), "user_id": ObjectId(user_id)}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation Not Found")

        updated_conversation = await db.conversations.find_one({"_id": ObjectId(id), "user_id": ObjectId(user_id)})
        updated_conversation["_id"] = str(updated_conversation["_id"])
        updated_conversation["user_id"] = str(updated_conversation["user_id"])
        updated_conversation["profile_id"] = str(updated_conversation["profile_id"])
        return updated_conversation
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while editing conversation in db: {str(e)}"
        )

async def delete_conversation_from_db(id, user_id):
    try:
        await db.conversations.delete_one({"_id": ObjectId(id), "user_id": ObjectId(user_id)})
        await db.chat_history.delete_many({"conversation_id": ObjectId(id), "user_id": ObjectId(user_id)})
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting conversation in db: {str(e)}"
        )