from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, learning, profiles, vocabulary

app = FastAPI(title="Serbian Vocabulary Trainer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(profiles.router)
app.include_router(vocabulary.router)
app.include_router(learning.router)
