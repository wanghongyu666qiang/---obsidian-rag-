/**
 * 智学 (ZhiXue) - 常量定义
 */

// View Types
export const CHAT_VIEW_TYPE = "zhixue-chat";
export const DASHBOARD_VIEW_TYPE = "zhixue-dashboard";
export const MODEL_SWITCH_VIEW_TYPE = "zhixue-model-switch";

// 默认配置
export const DEFAULT_SETTINGS: ZhiXueSettings = {
    backendPort: 18765,
    autoStartBackend: true,
    autoSaveConversation: true,
    conversationPath: "_zhixue/conversations",
    llmModel: "deepseek-ai/DeepSeek-V3",
    embeddingModel: "nomic-embed-text",
    embeddingSource: "ollama", // "ollama" | "cloud"
    embeddingBaseUrl: "",
    embeddingApiKey: "",
    ollamaUrl: "http://localhost:11434",
    ollamaApiKey: "ollama",
    llmBaseUrl: "",
    llmApiKey: "",
    // 多 API 配置（替代单独的 llmBaseUrl/llmApiKey）
    apiProfiles: [],
    aiName: "小智",
    homepageMode: "sidebar", // "sidebar" | "dashboard"
    showRibbonIcon: true,
    pythonPath: "",
    customApiModels: [],
};

// 数据目录
export const ZHIXUE_DIR = "_zhixue";
export const PROFILE_FILE = "ai-profile.md";
export const HABITS_FILE = "habits.json";
export const CONVERSATIONS_DIR = "conversations";

// 接口定义

// API 配置档案（支持多个，随时切换）
export interface ApiProfile {
    id: string;           // 唯一标识
    name: string;         // 显示名称，如"硅基流动-免费"
    baseUrl: string;      // API 地址
    apiKey: string;       // API Key
    isActive: boolean;    // 是否为当前激活的配置
}

export interface ZhiXueSettings {
    backendPort: number;
    autoStartBackend: boolean;
    autoSaveConversation: boolean;
    conversationPath: string;
    llmModel: string;
    embeddingModel: string;
    embeddingSource: "ollama" | "cloud";
    embeddingBaseUrl: string;
    embeddingApiKey: string;
    ollamaUrl: string;
    ollamaApiKey: string;
    // 新的多 API 配置（替代原来的 llmBaseUrl + llmApiKey）
    apiProfiles: ApiProfile[];
    // 保留旧字段用于向后兼容（逐步废弃）
    llmBaseUrl: string;
    llmApiKey: string;
    aiName: string;
    homepageMode: "sidebar" | "dashboard";
    showRibbonIcon: boolean;
    pythonPath: string;
    customApiModels: Array<{ name: string; label: string; provider: string }>;
}

export interface ChatMessage {
    role: "user" | "assistant";
    content: string;
    sources?: string[];
    timestamp: string;
}

export interface QueryResult {
    status?: string;  // "success" | "error"
    answer: string;
    sources: string[];
    related_notes: string[];
    mode: string;
    conversation_id?: string;
    error_type?: string;  // init_error / timeout / ollama_connection / model_missing / resource_error / query_error
    message?: string;  // 错误时的可读信息
    // 新增：RAG 检索上下文信息
    context_used?: boolean;
    retrieved_entities?: string[];
    retrieved_chunks?: string[];
}

export interface SystemStatus {
    status: string;
    version: string;
    rag: {
        initialized: boolean;
        indexing: boolean;
        indexed_files: number;
        working_dir: string;
        llm_model: string;
        embedding_model: string;
    };
    vault_path: string;
}

export interface HabitData {
    total_queries: number;
    topics: Record<string, { count: number; last_queried: string }>;
    frequent_notes: string[];
    query_history: Array<{
        time: string;
        query: string;
        notes_accessed?: string[];
    }>;
}

export interface AIProfileData {
    content: string;
    personality: string;
    about_user: string;
    special_instructions: string;
    path: string;
}

export interface OllamaModel {
    name: string;
    size_gb: number;
    modified: string;
}
