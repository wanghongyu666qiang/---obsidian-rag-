"""
智学 (ZhiXue) - 前后端共享 API 类型定义（Python 端）

这些 TypedDict 与后端 Pydantic 模型、前端 shared/api.ts 保持同步。
仅用于类型标注和文档，不参与运行时校验（运行时由 Pydantic 负责）。
"""

from typing import TypedDict, Optional, List, Dict, Any


# ─────────────────────────────────────────────
# 对话 API（/api/chat）
# ─────────────────────────────────────────────

class MessageItem(TypedDict):
    role: str          # "user" | "assistant"
    content: str


class QueryRequest(TypedDict):
    question: str
    mode: str                     # "hybrid" | "local" | "global" | "naive"
    conversation_id: Optional[str]
    current_note: Optional[str]   # 当前打开的笔记路径
    history: Optional[List[MessageItem]]


class SourceItem(TypedDict):
    file_path: str
    page: Optional[List[int]]
    excerpt: str


class QueryResponse(TypedDict):
    status: str                   # "success" | "error"
    answer: str
    sources: Optional[List[SourceItem]]
    related_notes: Optional[List[str]]
    mode: str
    conversation_id: Optional[str]
    error_type: Optional[str]
    message: Optional[str]


# ─────────────────────────────────────────────
# 文档摄取 API（/api/ingest）
# ─────────────────────────────────────────────

class IngestFileRequest(TypedDict):
    file_path: str


class IngestVaultRequest(TypedDict):
    force: bool


class IngestResult(TypedDict):
    status: str                   # "success" | "error" | "busy"
    message: Optional[str]
    files_processed: Optional[int]
    files_skipped: Optional[int]
    errors: Optional[int]
    total_files: Optional[int]


class RAGStatus(TypedDict):
    initialized: bool
    initializing: bool
    init_error: Optional[str]
    indexing: bool
    indexed_files: int
    working_dir: str
    llm_model: str
    embedding_model: str


# ─────────────────────────────────────────────
# AI 印象 API（/api/profile）
# ─────────────────────────────────────────────

class ProfileUpdateRequest(TypedDict):
    content: str


# ─────────────────────────────────────────────
# 系统 API（/api/system）
# ─────────────────────────────────────────────

class SwitchModelRequest(TypedDict):
    model_type: str               # "llm" | "embedding"
    model_name: str
    embedding_dim: Optional[int]


class UpdateConfigRequest(TypedDict):
    ollama_api_key: Optional[str]
    ollama_base_url: Optional[str]
    llm_base_url: Optional[str]
    llm_api_key: Optional[str]
    embedding_base_url: Optional[str]
    embedding_api_key: Optional[str]
    embedding_source: Optional[str]   # "ollama" | "cloud"


class SystemConfig(TypedDict):
    host: str
    port: int
    llm_model: str
    embedding_model: str
    ollama_base_url: str
    llm_base_url: str
    llm_api_key: str              # 脱敏显示
    active_llm_base_url: str
    active_llm_api_key: str      # 脱敏显示
    vault_path: str
    working_dir: str
    parser: str


class OllamaModelInfo(TypedDict):
    name: str
    size_gb: float
    modified: str


class CheckModelsResult(TypedDict):
    ollama_running: bool
    llm_model: Dict[str, Any]
    embedding_model: Dict[str, Any]
    instructions: List[str]
