from fastapi import HTTPException, status
from app.db.mongo import db
from bson import ObjectId


async def fetch_system_prompts():
    try:
        cursor = db.system_prompts.find()  
        prompts = await cursor.to_list(length=None)  
        if not prompts:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Prompts Found")
        
        return prompts
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching prompts: {str(e)}"
        )

async def add_system_prompt_to_db(category, prompt):
    try:
        categories = await fetch_categories()
        if category in categories:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category Already Exists")
        await db.system_prompts.insert_one({
            "category": category.strip().lower(),
            "prompt": prompt
        })
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding system prompt to db: {str(e)}"
        )
    

async def edit_prompt_in_db(id, update_data):
    try:
        object_id = ObjectId(id)
        # 🔒 normalize category if present
        if "category" in update_data and isinstance(update_data["category"], str):
            update_data["category"] = update_data["category"].strip().lower()
        result = await db.system_prompts.update_one({"_id": object_id}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")

        updated_prompt = await db.system_prompts.find_one({"_id": object_id})
        updated_prompt["_id"] = str(updated_prompt["_id"])
        return updated_prompt
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating prediction: {str(e)}"
        )
    

async def fetch_categories():
    try:
        categories = await db.system_prompts.distinct("category")
        return sorted(set(c.lower().strip() for c in categories))
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching categories: {str(e)}"
        )