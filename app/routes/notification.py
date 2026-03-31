from fastapi import APIRouter, Body, HTTPException, Depends, status
from app.deps.auth_deps import get_current_user
from app.services.notification_service import fetch_notifications, daily_morning_notification, mark_notification_as_read, night_reflection_notification, mystery_notification, fetch_notifications_for_admin, register_user_device_in_db, mark_all_notifications_as_read, push_test_notification_to_device, fetch_dashboard_notifications, mark_all_notifications_as_read_on_dashboard
from app.utils.admin import is_user_admin
from app.models.notification import RegisterDevicePayload, TestNotification

router = APIRouter()

@router.get("/")
async def get_notifications(current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        notifications = await fetch_notifications(user_id)
        return {"message": "Notifications Fetched Successfully", "result": notifications}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching notifications: {str(e)}"
        )

@router.get("/dashboard")
async def get_dashboard_notifications(current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")

        notifications = await fetch_dashboard_notifications()
        return {"message": "Notifications Fetched Successfully", "result": notifications}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching dashboard notifications: {str(e)}"
        )    

@router.patch("/{id}")
async def update_notification(id: str, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        await mark_notification_as_read(id, user_id)
        return {"message": "Notification Updated Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating notifications: {str(e)}"
        )

@router.patch("/")
async def update_all_notifications(current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        await mark_all_notifications_as_read(user_id)
        return {"message": "Notifications Updated Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating all notifications: {str(e)}"
        )
    

@router.patch("/dashboard")
async def update_all_notifications_on_dashboard(current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        await mark_all_notifications_as_read_on_dashboard()
        return {"message": "Notifications Updated Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while updating all notifications: {str(e)}"
        )

@router.post("/test/global")
async def test_global_notifications():

    await mystery_notification()  

    return {"message": "Global notifications created"}



@router.get("/dashboard/")
async def get_notifications_for_dashboard(current_user = Depends(get_current_user)):
    try:
        if not is_user_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this feature")
        
        notifications = await fetch_notifications_for_admin()
        return {"message": "Notifications Fetched Successfully", "result": notifications}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while fetching notifications for admin: {str(e)}"
        )
    

@router.post("/register-device/")
async def register_user_device(payload: RegisterDevicePayload, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        await register_user_device_in_db(payload, user_id)
        return {"message": "Device Registered Successfully"}
    
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while registering user device: {str(e)}"
        )
    

@router.post("/push/test")
async def push_test_notification(payload: TestNotification, current_user = Depends(get_current_user)):
    try:
        user_id = current_user["_id"]
        await push_test_notification_to_device(payload, user_id)
        return {"message": "Test Notification Pushed Successfully"}
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while pushing test notification: {str(e)}"
        )