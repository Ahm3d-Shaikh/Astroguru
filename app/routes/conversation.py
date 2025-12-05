from fastapi import APIRouter, HTTPException, status, Depends
from app.deps.auth_deps import get_current_user
from app.services.conversation_service import fetch_conversations, delete_conversation_from_db, edit_conversation_in_db
from app.models.conversation import ConversationUpdate
import json
from bson import json_util

router = APIRouter()


@router.get("/1")
async def get_conversations(current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        conversations = await fetch_conversations(user_id)
        result_json = json.loads(json_util.dumps(conversations))
        return {"message": "Conversations Fetched Successfully", "result": result_json}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching conversations: {str(e)}"
        )
    

@router.patch("/{id}")
async def edit_conversation(id: str, payload: ConversationUpdate, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        update_data = payload.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
        updated_conversation = await edit_conversation_in_db(id, user_id, update_data)
        return {"message": "Conversation Updated Successfully", "result": updated_conversation}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while editing conversation: {str(e)}"
        )

@router.delete("/{id}")
async def delete_conversation(id: str, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        await delete_conversation_from_db(id, user_id)
        return {"message": "Conversation Deleted Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting conversation: {str(e)}"
        )