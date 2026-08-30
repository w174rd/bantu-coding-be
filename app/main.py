from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai_provider_configs, conversations, personas, projects, tickets
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_provider_configs.router)
app.include_router(conversations.router)
app.include_router(personas.router)
app.include_router(projects.router)
app.include_router(tickets.router)
