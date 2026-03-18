from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services.notification_service import start_scheduler
from app.routes import astrology, auth, prompt, admin, report, prediction, user, profile, conversation, compatibility, subscription, notification

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# @app.on_event("startup")
# async def on_startup():
#     start_scheduler()

# @app.on_event("shutdown")
# async def on_shutdown():
#     scheduler = scheduler  # import from service if needed
#     scheduler.shutdown()

app.include_router(astrology.router, prefix="/astrology")
app.include_router(auth.router, prefix="/auth")
app.include_router(prompt.router, prefix="/system-prompt")
app.include_router(admin.router, prefix="/admin")
app.include_router(prediction.router, prefix="/prediction")
app.include_router(report.router, prefix="/report")
app.include_router(user.router, prefix="/user")
app.include_router(profile.router, prefix="/user/profile")
app.include_router(conversation.router, prefix="/conversation-list")
app.include_router(compatibility.router, prefix="/compatibility")
app.include_router(subscription.router, prefix="/subscription")
app.include_router(notification.router, prefix="/notification")

@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI project!"}

