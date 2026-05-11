from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import astrology, auth, prompt, admin, report, prediction, user, profile, conversation, compatibility, subscription, notification
from app.exception import validation_exception_handler
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from pymongo import ASCENDING, DESCENDING
from app.db.mongo import db
import logging

logger = logging.getLogger(__name__)

# (collection, keys, kwargs)
_INDEX_SPECS = [
    ("users", [("email", ASCENDING)], {}),
    ("users", [("phone", ASCENDING), ("country_code", ASCENDING)], {"unique": True}),
    ("users", [("role", ASCENDING), ("is_onboarded", ASCENDING)], {}),
    ("users", [("role", ASCENDING), ("is_onboarded", ASCENDING), ("created_at", DESCENDING)], {}),
    ("user_profiles", [("user_id", ASCENDING)], {}),
    ("user_reports", [("user_id", ASCENDING), ("profile_id", ASCENDING)], {}),
    ("user_reports", [("user_id", ASCENDING), ("report_id", ASCENDING), ("profile_id", ASCENDING)], {}),
    ("user_compatibility_reports", [("user_id", ASCENDING)], {}),
    ("user_compatibility_reports", [("user_id", ASCENDING), ("compatibility_id", ASCENDING)], {}),
    ("astrological_information", [("user_id", ASCENDING), ("profile_id", ASCENDING)], {}),
    ("conversations", [("user_id", ASCENDING), ("profile_id", ASCENDING)], {}),
    ("conversations", [("report_id", ASCENDING), ("user_id", ASCENDING), ("profile_id", ASCENDING), ("category", ASCENDING)], {}),
    ("chat_history", [("conversation_id", ASCENDING), ("user_id", ASCENDING)], {}),
    ("chat_history", [("conversation_id", ASCENDING), ("created_at", ASCENDING)], {}),
    ("notifications", [("user_id", ASCENDING), ("type", ASCENDING)], {}),
    ("notifications", [("status", ASCENDING), ("created_at", DESCENDING)], {}),
    ("user_wallet", [("user_id", ASCENDING)], {}),
    ("user_wallet", [("updated_at", DESCENDING)], {}),
    ("compatibilities", [("type", ASCENDING), ("is_comparison", ASCENDING)], {}),
]


async def _create_indexes():
    for coll, keys, kwargs in _INDEX_SPECS:
        try:
            await db[coll].create_index(keys, **kwargs)
        except Exception as e:
            # Don't block startup if a single index fails (e.g. pre-existing dupes for a unique index)
            logger.warning("Failed to create index on %s %s: %s", coll, keys, e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _create_indexes()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RequestValidationError, validation_exception_handler)

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
