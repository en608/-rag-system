import os

# 清除可能覆盖 .env 的系统环境变量
for key in ['OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_EMBEDDING_MODEL', 'OPENAI_LLM_MODEL']:
    os.environ.pop(key, None)

os.environ['PYTHONPATH'] = '.'

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )