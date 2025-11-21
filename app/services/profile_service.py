from fastapi import HTTPException, status
from app.db.mongo import db
from datetime import datetime
from bson import ObjectId

async def add_profile_to_db(payload, user_id):
    try:
        profile_doc = payload.dict()
        dob_date = profile_doc["date_of_birth"]          
        tob_time = profile_doc["time_of_birth"]          

        dob_str = dob_date.isoformat()                    
        tob_str = tob_time.strftime("%H:%M")              

        birth_timestamp = datetime(
            year=dob_date.year,
            month=dob_date.month,
            day=dob_date.day,
            hour=tob_time.hour,
            minute=tob_time.minute,
        )

        await db.user_profiles.insert_one({
            "user_id": ObjectId(user_id),
            "name":payload.name,
            "date_of_birth": dob_str,
            "time_of_birth": tob_str,
            "place_of_birth": payload.place_of_birth,
            "birth_timestamp": birth_timestamp,
            "gender": payload.gender,
            "lat": payload.lat,
            "long": payload.long
        })
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while adding profile to db: {str(e)}"
        )
    

async def get_profiles_for_user(user_id):
    try:
        cursor = db.user_profiles.find({"user_id": ObjectId(user_id)})
        profiles = await cursor.to_list(length=None)
        if not profiles:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Profiles Found For The User")
        
        return profiles
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user profiles: {str(e)}"
        )
    

async def get_specific_profile_from_db(id, user_id):
    try:
        profile = await db.user_profiles.find_one({"_id": ObjectId(id), "user_id": ObjectId(user_id)})
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile Not Found")
        
        profile["_id"] = str(profile["_id"])
        profile["user_id"] = str(profile["user_id"])
        return profile
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching user profile by id: {str(e)}"
        )
    

async def delete_user_profile_from_db(id, user_id):
    try:
        await db.user_profiles.delete_one({"_id": ObjectId(id), "user_id": ObjectId(user_id)})
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while deleting user profile: {str(e)}"
        )
    

async def edit_profile_in_db(id, user_id, update_data):
    try:
        object_id = ObjectId(id)
        update_fields = {}

        dob = update_data.get("date_of_birth")   
        tob = update_data.get("time_of_birth")   

        if dob:
            update_fields["date_of_birth"] = dob.isoformat()

        if tob:
            update_fields["time_of_birth"] = tob.strftime("%H:%M")

        if dob and tob:
            birth_timestamp = datetime(
                year=dob.year,
                month=dob.month,
                day=dob.day,
                hour=tob.hour,
                minute=tob.minute,
            )
            update_fields["birth_timestamp"] = birth_timestamp

        for field in ["name", "gender", "lat", "long", "place_of_birth"]:
            if field in update_data and update_data[field] is not None:
                update_fields[field] = update_data[field]

            
        result = await db.user_profiles.update_one({"_id": object_id, "user_id": ObjectId(user_id)}, {"$set": update_fields})
        if result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

        updated_profile = await db.user_profiles.find_one({"_id": object_id, "user_id": ObjectId(user_id)})
        updated_profile["_id"] = str(updated_profile["_id"])
        updated_profile["user_id"] = str(updated_profile["user_id"])
        return updated_profile
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while editing user profile: {str(e)}"
        )