# 智学 (ZhiXue) 后端

FastAPI 后端服务，提供 RAG 知识库、LLM 对话、笔记摄取等功能。

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置

复制 `.env.example` 为 `.env`，按需修改：

```bash
cp .env.example .env
```

关键配置项：
- `ZHIXUE_VAULT_PATH` - Obsidian Vault 路径（自动检测若留空）
- `ZHIXUE_PORT` - 服务端口（默认 18765）
- `ZHIXUE_LLM_MODEL` - LLM 模型名（如 `deepseek-r1:7b` 或 `deepseek-ai/DeepSeek-V3`）
- `LLM_BASE_URL` / `LLM_API_KEY` - 云端 LLM 配置（可选）
- `ZHIXUE_EMBEDDING_MODEL` - Embedding 模型（默认 `nomic-embed-text`）

### 3. 启动

```bash
python start.py
```

后端会自动：
- 创建 `.env`（若不存在）
- 检测 Vault 路径
- 初始化 RAG 引擎（后台异步）
- 校验配置并输出结果

## API 端点

### 系统 `/api/system`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/system/status` | GET | 系统状态（含 RAG 引擎状态） |
| `/api/system/config` | GET | 当前配置（API Key 脱敏） |
| `/api/system/check-models` | GET | 检查 Ollama 模型安装状态 |
| `/api/system/list-models` | GET | 列出 Ollama 已安装模型 |
| `/api/system/switch-model` | PUT | 运行时切换 LLM/Embedding 模型 |
| `/api/system/update-config` | PUT | 更新配置（API Key、地址等） |

### 对话 `/api/chat`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat/query` | POST | RAG 增强查询（含知识库检索） |
| `/api/chat/raw-llm` | POST | 纯 LLM 查询（绕过 RAG） |

### 摄取 `/api/ingest`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/ingest/file` | POST | 摄取单个文件 |
| `/api/ingest/vault` | POST | 摄取整个 Vault（`{"force": true}` 强制重索引） |
| `/api/ingest/status` | GET | 获取摄取状态（含进度信息） |

### 其他

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/profile/*` | - | AI 印象管理 |
| `/api/habits/*` | - | 使用习惯追踪 |

## 多模型索引隔离

索引按 **Embedding 模型 + Vault 路径** 自动隔离：

```
_zhixue/rag_storage/
├── nomic-embed-text_abc12345/   # Vault A，模型 nomic-embed-text
├── nomic-embed-text_def67890/   # Vault B，模型 nomic-embed-text
└── BAAI_bge-m3_abc12345/      # Vault A，模型 BAAI/bge-m3
```

切换模型或 Vault 时，自动使用对应索引目录，互不干扰。

## 配置校验

启动时自动校验：
- Vault 路径是否存在
- 端口号是否有效
- Embedding/LLM 配置是否完整
- 工作目录是否可创建

校验失败会打印错误日志，但不阻止启动（方便调试）。

## 测试

```bash
# 安装测试依赖
pip install pytest pytest-cov

# 运行所有测试
pytest -v

# 带覆盖率
pytest --cov=app --cov-report=html
```

测试覆盖：
- 配置校验逻辑
- RAG 引擎独立功能（使用 mock，不加载重型依赖）

## 项目结构

```
backend/
├── app/
│   ├── main.py          # FastAPI 入口（含 lifespan）
│   ├── config.py        # 配置管理（含自动检测、多模型隔离）
│   ├── rag_engine.py    # RAG 引擎封装（含页码映射）
│   ├── ai_profile.py    # AI 印象管理
│   ├── habit_tracker.py # 使用习惯追踪
│   └── routers/        # API 路由
│       ├── chat.py
│       ├── ingest.py
│       ├── profile.py
│       ├── habits.py
│       └── system.py
├── start.py             # 启动脚本
├── requirements.txt     # Python 依赖
├── .env.example        # 配置模板
└── tests/              # 测试套件
    ├── conftest.py
    ├── test_config.py
    └── test_rag_engine.py
```

## 依赖说明

- **FastAPI** - Web 框架
- **RAGAnything** - RAG 文档处理（含 MinerU PDF 解析）
- **LightRAG** - 知识图谱 + 向量检索
- **httpx** - 异步 HTTP 客户端（调用 LLM API）
- **python-dotenv** - `.env` 配置加载
