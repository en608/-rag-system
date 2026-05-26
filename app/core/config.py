"""应用配置：从环境变量加载数据库与 OpenAI 相关设置。"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# 强制从 .env 文件加载，覆盖系统环境变量
load_dotenv(override=True)


class Settings(BaseSettings):
    """全局配置项，通过 .env 文件或环境变量注入。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RAG System V1.0"
    debug: bool = False

    # 异步 PostgreSQL 连接串
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rag_db"

    # 数据库连接池配置
    db_pool_size: int = 20  # 连接池大小
    db_max_overflow: int = 10  # 超出pool_size后最多可创建的连接数
    db_pool_timeout: int = 30  # 获取连接的超时时间（秒）
    db_pool_recycle: int = 1800  # 连接回收时间（秒），避免长时间空闲连接断开

    # OpenAI API
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_llm_model: str = "gpt-4o-mini"

    # 文本切分参数（与 RecursiveCharacterTextSplitter 一致）
    chunk_size: int = 500
    chunk_overlap: int = 50

    # 向量检索 Top-K
    retrieval_top_k: int = 5

    # 向量维度（text-embedding-3-small 默认 1536）
    embedding_dimension: int = 1536

    # Rerank模型配置
    rerank_model: str = "BAAI/bge-reranker-base-m3"  # 轻量模型
    rerank_max_length: int = 512
    rerank_batch_size: int = 32

    # 异步推理配置
    rerank_async_enabled: bool = True
    rerank_queue_size: int = 100
    rerank_workers: int = 2

    # JWT 认证密钥
    secret_key: str = "your-secret-key-change-in-production"

    # API限流配置
    rate_limit_enabled: bool = True
    rate_limit_default: str = "60/minute"  # 默认限流：每分钟60次
    rate_limit_auth: str = "10/minute"  # 认证接口限流：每分钟10次
    rate_limit_upload: str = "5/minute"  # 上传接口限流：每分钟5次
    rate_limit_chat: str = "20/minute"  # 问答接口限流：每分钟20次

    # CORS配置
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: list[str] = ["*"]

    # 安全配置
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]


@lru_cache
def get_settings() -> Settings:
    """单例配置，避免重复解析环境变量。"""
    return Settings()
