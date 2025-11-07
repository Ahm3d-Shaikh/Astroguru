from fastapi import HTTPException, status
from app.db.mongo import db


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
        await db.system_prompts.insert_one({
            "category": category,
            "prompt": prompt
        })
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding system prompt to db: {str(e)}"
        )