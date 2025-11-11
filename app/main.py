from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import astrology, auth, prompt, admin, report, prediction

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(astrology.router, prefix="/astrology")
app.include_router(auth.router, prefix="/auth")
app.include_router(prompt.router, prefix="/system-prompt")
app.include_router(admin.router, prefix="/admin")
app.include_router(prediction.router, prefix="/prediction")
app.include_router(report.router, prefix="/report")

@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI project!"}

