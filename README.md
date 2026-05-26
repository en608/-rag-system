# RAG 智能问答系统 V1.0

基于检索增强生成（RAG）的企业级智能问答系统，支持文档上传、向量化存储、智能检索和流式问答。

## 功能特性

- **文档管理**：支持上传 TXT/PDF 文件，自动解析、切分、向量化入库
- **智能检索**：基于 pgvector 的向量相似度检索 + Rerank 重排序
- **流式问答**：SSE 流式输出，支持多轮对话上下文
- **用户隔离**：多租户设计，每个用户只能访问自己的文档
- **安全认证**：JWT Token 认证 + API 限流

## 技术栈

| 层次 | 技术 | 作用 |
|------|------|------|
| Web 框架 | FastAPI | 异步 HTTP 服务 |
| 数据库 | PostgreSQL 16 + pgvector | 向量存储与检索 |
| ORM | SQLAlchemy 2.0 (async) | 数据库操作 |
| LLM 框架 | LangChain | LLM 调用与链式处理 |
| Embedding | text2vec-base-chinese | 本地文本向量化 (768维) |
| Rerank | bge-reranker-base | 检索结果重排序 |
| 容器化 | Docker + Docker Compose | 一键部署 |
| 反向代理 | Nginx | 负载均衡与限流 |

## 快速开始

### 方式一：Docker 部署（推荐）

#### 1. 克隆项目

```bash
git clone https://github.com/your-username/rag-system.git
cd rag-system
```

#### 2. 配置环境变量

复制并编辑环境变量文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入以下配置：

```env
# 数据库配置
DB_PASSWORD=your_secure_password

# LLM API 配置（以小米 MiMo 为例）
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
OPENAI_LLM_MODEL=mimo-v2.5-pro

# 应用配置
SECRET_KEY=your_secret_key_here
```

#### 3. 启动服务

```bash
docker compose up -d
```

#### 4. 访问系统

- **用户界面**：http://localhost
- **API 文档**：http://localhost:8080/docs

#### 5. 停止服务

```bash
docker compose down
```

### 方式二：本地开发

#### 1. 准备 PostgreSQL

```bash
# 创建数据库
createdb -U postgres -p 5433 rag_db

# 启用 pgvector 扩展
psql -U postgres -p 5433 -d rag_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### 2. 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

#### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件
```

#### 4. 执行数据库迁移

```bash
alembic upgrade head
```

#### 5. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/users/register` | 用户注册 |
| POST | `/api/v1/users/login` | 用户登录 |
| POST | `/api/v1/documents/upload` | 上传文档 |
| GET | `/api/v1/documents/list` | 文档列表 |
| DELETE | `/api/v1/documents/{id}` | 删除文档 |
| GET | `/api/v1/documents/{id}/preview` | 预览文档 |
| POST | `/api/v1/chat/retrieve` | 检索相关片段 |
| POST | `/api/v1/chat/stream` | 流式问答 |
| GET | `/health` | 健康检查 |

### 使用示例

#### 注册用户

```bash
curl -X POST "http://localhost:8080/api/v1/users/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "test123456"}'
```

#### 上传文档

```bash
curl -X POST "http://localhost:8080/api/v1/documents/upload" \
  -H "Authorization: Bearer {your_token}" \
  -F "file=@document.txt"
```

#### 流式问答

```bash
curl -X POST "http://localhost:8080/api/v1/chat/stream" \
  -H "Authorization: Bearer {your_token}" \
  -H "Content-Type: application/json" \
  -d '{"question": "文档的主要内容是什么？", "chat_history": []}'
```

## 项目结构

```
rag-system/
├── alembic/                    # 数据库迁移
│   └── versions/
│       ├── 001_initial_schema.py
│       ├── 002_add_password_hash.py
│       └── 003_add_pgvector.py
├── app/                        # 应用代码
│   ├── api/v1/                 # API 路由
│   │   ├── users.py            # 用户接口
│   │   ├── documents.py        # 文档接口
│   │   └── chat.py             # 问答接口
│   ├── core/                   # 核心配置
│   │   ├── config.py           # 配置管理
│   │   ├── database.py         # 数据库连接
│   │   └── deps.py             # 依赖注入
│   ├── models/                 # 数据库模型
│   ├── schemas/                # 请求/响应模型
│   ├── services/               # 业务逻辑
│   │   ├── document_service.py # 文档处理
│   │   ├── embedding_service.py# 向量化服务
│   │   ├── rag_service.py      # RAG 核心逻辑
│   │   └── rerank_service.py   # 重排序服务
│   ├── utils/                  # 工具函数
│   └── static/                 # 前端页面
├── nginx/                      # Nginx 配置
├── scripts/                    # 脚本工具
├── docker-compose.yml          # Docker 编排
├── Dockerfile                  # Docker 镜像
├── requirements.txt            # Python 依赖
└── .env.example                # 环境变量模板
```

## 核心流程

### 文档上传流程

```
上传文件 → 解析文本 → 切分片段 → 向量化 → 写入数据库
```

### RAG 问答流程

```
用户提问 → 问题向量化 → 向量检索 → Rerank重排序 → 拼接上下文 → LLM生成回答
```

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DB_PASSWORD` | 数据库密码 | postgres |
| `OPENAI_API_KEY` | LLM API 密钥 | - |
| `OPENAI_BASE_URL` | LLM API 地址 | https://api.openai.com/v1 |
| `OPENAI_LLM_MODEL` | LLM 模型名 | gpt-4o-mini |
| `SECRET_KEY` | JWT 密钥 | - |
| `RERANK_MODEL` | Rerank 模型 | BAAI/bge-reranker-base |

### 文本切分参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `CHUNK_SIZE` | 每个片段最大字符数 | 500 |
| `CHUNK_OVERLAP` | 相邻片段重叠字符数 | 50 |
| `RETRIEVAL_TOP_K` | 检索返回的片段数量 | 5 |

## 安全特性

- **JWT 认证**：用户登录后获取 Token，所有 API 请求需携带
- **API 限流**：使用 slowapi 实现请求频率限制
- **密码加密**：使用 bcrypt 加密存储用户密码
- **用户隔离**：每个用户只能访问自己的文档

## 性能优化

- **向量检索**：使用 pgvector 的 HNSW 索引加速检索
- **Rerank 重排序**：使用 Cross-Encoder 模型提升检索精度
- **连接池**：数据库连接池复用，减少连接开销
- **流式输出**：SSE 流式返回，提升用户体验

## 后续规划

- [ ] 混合检索（向量 + BM25）
- [ ] 查询优化（查询改写、扩展）
- [ ] 上下文压缩（去重、关键句提取）
- [ ] GPU 加速推理
- [ ] 结果缓存机制
- [ ] HTTPS 支持
- [ ] 监控与日志系统

## 许可证

MIT License

## 联系方式

如有问题或建议，欢迎提交 Issue 或 Pull Request。
