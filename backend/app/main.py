import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, catalog, chat
from app.config import settings
from app.providers import factory

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Ask Dr. Beauty API", version="0.1.0",
              description="Concept demo for Dr. Beauty Care. Not the official store.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(catalog.router)
app.include_router(chat.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"ok": True, "provider": factory.active_name(), "available": factory.available()}
