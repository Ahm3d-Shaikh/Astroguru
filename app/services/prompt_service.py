from fastapi import HTTPException, status
from app.db.mongo import db

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