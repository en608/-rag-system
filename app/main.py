"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers, setup_logging
from app.core.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动与关闭时的钩子（V1.0 仅作占位）。"""
    yield


def create_app() -> FastAPI:
    """应用工厂：便于测试与多实例部署。"""
    # 配置日志系统
    setup_logging()

    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="企业级 RAG 系统 V1.0 - 基础端到端检索增强生成",
        lifespan=lifespan,
    )

    # 配置限流器
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # 注册全局错误处理中间件
    register_error_handlers(app)

    # 配置CORS（生产环境应限制origins）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins if not settings.debug else ["*"],
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # 配置受信任的主机（防止Host头攻击）
    if not settings.debug:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_hosts,
        )

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["health"])
    async def health_check():
        """健康检查接口。"""
        return {"status": "ok", "app": settings.app_name}

    @app.get("/", tags=["home"])
    async def home():
        """主页：RAG 问答系统界面。"""
        return FileResponse(Path("app/static/index.html"))

    return app


app = create_app()
