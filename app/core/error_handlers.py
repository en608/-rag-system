"""全局错误处理中间件。"""

import logging
import time
import traceback
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class AppError(Exception):
    """应用自定义异常基类。"""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Any = None,
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppError):
    """资源未找到异常。"""

    def __init__(self, message: str = "资源未找到", detail: Any = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class ValidationError(AppError):
    """数据验证异常。"""

    def __init__(self, message: str = "数据验证失败", detail: Any = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


class AuthenticationError(AppError):
    """认证异常。"""

    def __init__(self, message: str = "认证失败", detail: Any = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


class AuthorizationError(AppError):
    """授权异常。"""

    def __init__(self, message: str = "权限不足", detail: Any = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


def register_error_handlers(app: FastAPI) -> None:
    """注册全局错误处理中间件。"""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """处理应用自定义异常。"""
        logger.warning(
            f"AppError: {exc.message} | "
            f"Path: {request.url.path} | "
            f"Method: {request.method} | "
            f"Detail: {exc.detail}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "detail": exc.detail,
                "path": request.url.path,
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        """处理数据库异常。"""
        logger.error(
            f"Database error: {str(exc)} | "
            f"Path: {request.url.path} | "
            f"Method: {request.method}\n"
            f"{traceback.format_exc()}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "数据库错误",
                "detail": "请稍后重试或联系管理员",
                "path": request.url.path,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """处理未捕获的异常。"""
        logger.error(
            f"Unhandled exception: {str(exc)} | "
            f"Path: {request.url.path} | "
            f"Method: {request.method}\n"
            f"{traceback.format_exc()}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "服务器内部错误",
                "detail": "请稍后重试或联系管理员",
                "path": request.url.path,
            },
        )


def setup_logging() -> None:
    """配置日志系统。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # 设置第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
