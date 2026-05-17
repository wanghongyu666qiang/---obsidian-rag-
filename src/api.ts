/**
 * 智学 (ZhiXue) - 前后端共享 API 类型定义
 *
 * 这些接口与后端 Pydantic 模型保持同步。
 * 前端 import 路径：../shared/api （需构建配置支持）
 * 或手动复制到 plugin/src/types/api.ts
 */

// ─────────────────────────────────────────────
// 对话 API（/api/chat）
// ─────────────────────────────────────────────

export interface MessageItem {
  role: "user" | "assistant";
  content: string;
}

export interface QueryRequest {
  question: string;
  mode?: "hybrid" | "local" | "global" | "naive";
  conversation_id?: string | null;
  current_note?: string | null;
  history?: MessageItem[];
}

export interface SourceItem {
  file_path: string;
  page?: number[];
  excerpt: string;
}

export interface QueryResponse {
  status: "success" | "error";
  answer: string;
  sources?: SourceItem[];
  related_notes?: string[];
  mode?: string;
  conversation_id?: string | null;
  context_used?: boolean;
  retrieved_entities?: unknown[];
  retrieved_chunks?: unknown[];
  error_type?: string | null;
  message?: string | null;
}

// ─────────────────────────────────────────────
// 文档摄取 API（/api/ingest）
// ─────────────────────────────────────────────

export interface IngestFileRequest {
  file_path: string;
}

export interface IngestVaultRequest {
  force?: boolean;
}

export interface IngestResult {
  status: "success" | "error" | "busy";
  message?: string;
  files_processed?: number;
  files_skipped?: number;
  errors?: number;
  total_files?: number;
}

export interface RAGStatus {
  initialized: boolean;
  initializing: boolean;
  init_error: string | null;
  indexing: boolean;
  indexed_files: number;
  working_dir: string;
  llm_model: string;
  embedding_model: string;
}

// ─────────────────────────────────────────────
// AI 印象 API（/api/profile）
// ─────────────────────────────────────────────

export interface ProfileUpdateRequest {
  content: string;
}

export interface ProfileResponse {
  status?: string;
  content?: string;
  message?: string;
}

// ─────────────────────────────────────────────
// 使用习惯 API（/api/habits）
// ─────────────────────────────────────────────

export interface HabitsData {
  [key: string]: unknown;
}

export interface Recommendations {
  frequent_notes?: string[];
  [key: string]: unknown;
}

// ─────────────────────────────────────────────
// 系统 API（/api/system）
// ─────────────────────────────────────────────

export interface SwitchModelRequest {
  model_type: "llm" | "embedding";
  model_name: string;
  embedding_dim?: number | null;
}

export interface UpdateConfigRequest {
  ollama_api_key?: string | null;
  ollama_base_url?: string | null;
  llm_base_url?: string | null;
  llm_api_key?: string | null;
  embedding_base_url?: string | null;
  embedding_api_key?: string | null;
  embedding_source?: "ollama" | "cloud" | null;
}

export interface SystemStatus {
  status: string;
  version: string;
  rag: RAGStatus;
  vault_path: string;
}

export interface SystemConfig {
  host: string;
  port: number;
  llm_model: string;
  embedding_model: string;
  ollama_base_url: string;
  llm_base_url: string;
  llm_api_key: string;         // 脱敏显示，如 "***ABCD"
  active_llm_base_url: string;
  active_llm_api_key: string;   // 脱敏显示
  vault_path: string;
  working_dir: string;
  parser: string;
}

export interface OllamaModelInfo {
  name: string;
  size_gb: number;
  modified: string;
}

export interface CheckModelsResult {
  ollama_running: boolean;
  llm_model: { name: string; installed: boolean };
  embedding_model: { name: string; installed: boolean };
  instructions: string[];
}

export interface ListModelsResult {
  ollama_running: boolean;
  models: OllamaModelInfo[];
  current_llm: string;
  current_embedding: string;
  error?: string;
}

// ─────────────────────────────────────────────
// 通用 API 响应包装
// ─────────────────────────────────────────────

export interface ApiResponse<T = unknown> {
  status: "ok" | "success" | "error";
  message?: string;
  [key: string]: unknown;
}
