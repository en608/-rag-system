"""V1 路由聚合。"""

from fastapi import APIRouter

from app.api.v1 import chat, documents, users

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(documents.router)
api_router.include_router(chat.router)
