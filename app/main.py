from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import astrology, auth

app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(astrology.router, prefix="/astrology")
app.include_router(auth.router, prefix="/auth")

@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI project!"}

