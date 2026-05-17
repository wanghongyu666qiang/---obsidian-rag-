/**
 * 智学 (ZhiXue) - 模型切换可视化面板
 * 展示 Ollama 已安装模型，支持一键切换 LLM / Embedding
 */

import { ItemView, WorkspaceLeaf, Notice, Modal } from "obsidian";
import { MODEL_SWITCH_VIEW_TYPE, type ZhiXueSettings, type OllamaModel } from "../utils/constants";
import { BackendClient } from "../services/BackendClient";

export class ModelSwitchView extends ItemView {
    private settings: ZhiXueSettings;
    private backendClient: BackendClient;
    private models: OllamaModel[] = [];
    private ollamaRunning = false;
    private currentLLM = "";
    private currentEmbedding = "";
    private isLoading = false;
    private plugin: any;

    constructor(
        leaf: WorkspaceLeaf,
        settings: ZhiXueSettings,
        backendClient: BackendClient,
        plugin: any
    ) {
        super(leaf);
        this.settings = settings;
        this.backendClient = backendClient;
        this.plugin = plugin;
    }

    getViewType() {
        return MODEL_SWITCH_VIEW_TYPE;
    }

    getDisplayText() {
        return "智学 · 模型管理";
    }

    getIcon() {
        return "brain";
    }

    async onOpen() {
        await this.render();
    }

    // 云端 API 模型预设
    private API_MODEL_PRESETS = [
        { name: "Qwen/Qwen2.5-14B-Instruct", label: "Qwen2.5 14B", provider: "SiliconFlow" },
        { name: "deepseek-ai/DeepSeek-V3", label: "DeepSeek-V3", provider: "SiliconFlow" },
        { name: "Qwen/Qwen2.5-7B-Instruct", label: "Qwen2.5 7B", provider: "SiliconFlow" },
        { name: "THUDM/glm-4-9b-chat", label: "GLM-4 9B", provider: "SiliconFlow" },
        { name: "google/gemini-1.5-flash", label: "Gemini 1.5 Flash", provider: "Google" },
        { name: "google/gemini-1.5-pro", label: "Gemini 1.5 Pro", provider: "Google" },
    ];

    async render() {
        this.containerEl.empty();

        // === 顶部标题栏 ===
        const headerEl = this.containerEl.createDiv({ cls: "zhixue-model-header" });
        headerEl.createSpan({ cls: "zhixue-model-title", text: "🧠 模型管理" });

        const headerRight = headerEl.createDiv({ cls: "zhixue-model-header-right" });

        // Ollama 状态指示
        const statusDot = headerRight.createSpan({ cls: "zhixue-model-status-dot" });
        const statusText = headerRight.createSpan({ cls: "zhixue-model-status-text" });

        // 刷新按钮
        const refreshBtn = headerRight.createEl("button", {
            cls: "zhixue-model-refresh-btn",
            text: "🔄 刷新",
        });
        refreshBtn.addEventListener("click", () => this.refreshModels());

        // === 内容区 ===
        const contentEl = this.containerEl.createDiv({ cls: "zhixue-model-content" });

        // 加载状态
        if (this.isLoading) {
            contentEl.createDiv({ cls: "zhixue-model-loading", text: "正在获取模型列表..." });
            return;
        }

        // 未加载过数据，先加载
        if (this.models.length === 0 && this.currentLLM === "" && !this._hasRefreshed) {
            this.isLoading = true;
            await this.refreshModels();
            return;
        }

        // Ollama 状态显示（不再阻塞后续渲染）
        if (this.ollamaRunning) {
            statusDot.addClass("zhixue-model-status-online");
            statusText.setText("Ollama 已连接");
        } else {
            statusDot.addClass("zhixue-model-status-offline");
            statusText.setText("Ollama 未连接");
        }

        // === 当前 API 状态 ===
        const activeProfile = this.settings.apiProfiles.find(p => p.isActive);
        const apiSection = contentEl.createDiv({ cls: "zhixue-model-section" });
        const apiHeader = apiSection.createDiv({ cls: "zhixue-model-section-header" });
        apiHeader.createSpan({ cls: "zhixue-model-section-title", text: "🔗 当前 API" });
        const apiInfo = apiSection.createDiv({ cls: "zhixue-model-api-info" });
        if (activeProfile) {
            apiInfo.createSpan({ text: `云端: ${activeProfile.name}（${activeProfile.baseUrl}）` });
            apiInfo.createEl("div", {
                cls: "zhixue-model-hint",
                text: `💡 当前模型: ${this.settings.llmModel || "未设置"}`,
            });
        } else {
            apiInfo.createSpan({ text: `本地 Ollama（${this.settings.ollamaUrl}）` });
        }

        // === 云端模型区（始终显示，不依赖 Ollama）===
        this.renderCloudModelSection(contentEl);

        // === 本地 Ollama 模型区 ===
        if (this.ollamaRunning) {
            this.renderModelSection(contentEl, "llm", "🗣️ 本地对话模型 (LLM)", "用于 AI 对话和问答");
            this.renderModelSection(contentEl, "embedding", "📐 本地向量模型 (Embedding)", "用于知识库检索和语义匹配");
        } else {
            // Ollama 未运行时显示提示
            const ollamaSection = contentEl.createDiv({ cls: "zhixue-model-section" });
            const ollamaHeader = ollamaSection.createDiv({ cls: "zhixue-model-section-header" });
            ollamaHeader.createSpan({ cls: "zhixue-model-section-title", text: "💻 本地 Ollama 模型" });
            ollamaSection.createDiv({ cls: "zhixue-model-offline", text: "⚠️ Ollama 未连接" });
            ollamaSection.createDiv({
                cls: "zhixue-model-hint",
                text: "请确认 Ollama 正在运行，然后点击「刷新」重试。如只使用云端模型，可忽略此提示。",
            });
        }

        // === 连接配置 ===
        this.renderConnectionConfig(contentEl);

        // === 底部提示 ===
        const footerEl = contentEl.createDiv({ cls: "zhixue-model-footer" });
        if (this.ollamaRunning) {
            footerEl.createSpan({ text: "💡 安装新模型：终端运行 " });
            footerEl.createEl("code", { text: "ollama pull <模型名>" });
            footerEl.createSpan({ text: "，然后点击「刷新」" });
        }
    }

    private _hasRefreshed = false;

    private renderModelSection(
        parent: HTMLElement,
        modelType: "llm" | "embedding",
        title: string,
        description: string
    ) {
        const sectionEl = parent.createDiv({ cls: "zhixue-model-section" });

        // 标题
        const sectionHeader = sectionEl.createDiv({ cls: "zhixue-model-section-header" });
        sectionHeader.createSpan({ cls: "zhixue-model-section-title", text: title });
        sectionHeader.createSpan({ cls: "zhixue-model-section-desc", text: description });

        // 当前模型
        const currentModel = modelType === "llm" ? this.currentLLM : this.currentEmbedding;
        const currentEl = sectionEl.createDiv({ cls: "zhixue-model-current" });
        currentEl.createSpan({ text: "当前：" });
        currentEl.createEl("strong", { text: currentModel || "未设置" });

        // 模型卡片列表
        const cardsEl = sectionEl.createDiv({ cls: "zhixue-model-cards" });

        // 判断哪些模型适合作为 LLM 或 Embedding
        const filteredModels = this.filterModels(modelType);

        if (filteredModels.length === 0) {
            cardsEl.createDiv({
                cls: "zhixue-model-empty",
                text: modelType === "llm"
                    ? "未找到对话模型，请用 ollama pull 安装"
                    : "未找到向量模型，请安装如 nomic-embed-text",
            });
        }

        for (const model of filteredModels) {
            const isActive = model.name === currentModel;
            const cardEl = cardsEl.createDiv({
                cls: `zhixue-model-card ${isActive ? "zhixue-model-card-active" : ""}`,
            });

            // 卡片左侧信息
            const infoEl = cardEl.createDiv({ cls: "zhixue-model-card-info" });
            infoEl.createDiv({ cls: "zhixue-model-card-name", text: model.name });
            const metaEl = infoEl.createDiv({ cls: "zhixue-model-card-meta" });
            if (model.size_gb > 0) {
                metaEl.createSpan({ text: `${model.size_gb} GB` });
            }
            if (model.modified) {
                const date = model.modified.split("T")[0];
                metaEl.createSpan({ text: ` · ${date}` });
            }

            // 卡片右侧操作
            if (isActive) {
                cardEl.createDiv({ cls: "zhixue-model-card-badge", text: "✓ 当前" });
            } else {
                const switchBtn = cardEl.createEl("button", {
                    cls: "zhixue-model-card-btn",
                    text: "切换",
                });
                switchBtn.addEventListener("click", async () => {
                    await this.handleSwitch(modelType, model.name);
                });
            }
        }

        // 手动输入区域
        const customEl = sectionEl.createDiv({ cls: "zhixue-model-custom" });
        const isCloud = this.settings.apiProfiles.some(p => p.isActive);
        const inputEl = customEl.createEl("input", {
            cls: "zhixue-model-custom-input",
            attr: {
                type: "text",
                placeholder: isCloud
                    ? "硅基流动模型，如 deepseek-ai/DeepSeek-V3"
                    : "输入模型名称，如 qwen2.5:7b",
            },
        });
        const customBtn = customEl.createEl("button", {
            cls: "zhixue-model-custom-btn",
            text: "切换",
        });
        customBtn.addEventListener("click", async () => {
            const name = (inputEl as HTMLInputElement).value.trim();
            if (name) {
                await this.handleSwitch(modelType, name);
            }
        });
    }

    /**
     * 渲染云端模型区域（预设 + 自定义，不依赖 Ollama）
     */
    private renderCloudModelSection(parent: HTMLElement) {
        const sectionEl = parent.createDiv({ cls: "zhixue-model-section" });
        const sectionHeader = sectionEl.createDiv({ cls: "zhixue-model-section-header" });
        sectionHeader.createSpan({ cls: "zhixue-model-section-title", text: "☁️ 云端模型" });
        sectionHeader.createSpan({ cls: "zhixue-model-section-desc", text: "通过 API 调用的云端大模型" });

        const currentLLM = this.settings.llmModel;
        const cardsEl = sectionEl.createDiv({ cls: "zhixue-model-cards" });

        // 当前模型高亮显示
        const currentEl = sectionEl.createDiv({ cls: "zhixue-model-current" });
        currentEl.createSpan({ text: "当前对话模型：" });
        currentEl.createEl("strong", { text: currentLLM || "未设置" });

        // === 预设云端模型 ===
        for (const preset of this.API_MODEL_PRESETS) {
            const isActive = preset.name === currentLLM;
            const cardEl = cardsEl.createDiv({
                cls: `zhixue-model-card ${isActive ? "zhixue-model-card-active" : ""}`,
            });

            const infoEl = cardEl.createDiv({ cls: "zhixue-model-card-info" });
            infoEl.createDiv({ cls: "zhixue-model-card-name", text: preset.label });
            const metaEl = infoEl.createDiv({ cls: "zhixue-model-card-meta" });
            metaEl.createSpan({ text: preset.provider });

            if (isActive) {
                cardEl.createDiv({ cls: "zhixue-model-card-badge", text: "✓ 当前" });
            } else {
                const switchBtn = cardEl.createEl("button", {
                    cls: "zhixue-model-card-btn",
                    text: "切换",
                });
                switchBtn.addEventListener("click", async () => {
                    await this.handleCloudModelSwitch(preset.name);
                });
            }
        }

        // === 自定义模型 ===
        const customModels = this.settings.customApiModels || [];
        if (customModels.length > 0) {
            for (const custom of customModels) {
                const isActive = custom.name === currentLLM;
                const cardEl = cardsEl.createDiv({
                    cls: `zhixue-model-card ${isActive ? "zhixue-model-card-active" : ""}`,
                });

                const infoEl = cardEl.createDiv({ cls: "zhixue-model-card-info" });
                infoEl.createDiv({ cls: "zhixue-model-card-name", text: custom.label });
                const metaEl = infoEl.createDiv({ cls: "zhixue-model-card-meta" });
                metaEl.createSpan({ text: custom.provider || "自定义" });

                if (isActive) {
                    cardEl.createDiv({ cls: "zhixue-model-card-badge", text: "✓ 当前" });
                } else {
                    const switchBtn = cardEl.createEl("button", {
                        cls: "zhixue-model-card-btn",
                        text: "切换",
                    });
                    switchBtn.addEventListener("click", async () => {
                        await this.handleCloudModelSwitch(custom.name);
                    });
                }
            }
        }

        // === 手动输入 ===
        const customEl = sectionEl.createDiv({ cls: "zhixue-model-custom" });
        const inputEl = customEl.createEl("input", {
            cls: "zhixue-model-custom-input",
            attr: {
                type: "text",
                placeholder: "输入云端模型名称，如 deepseek-ai/DeepSeek-V3",
            },
        });
        const customBtn = customEl.createEl("button", {
            cls: "zhixue-model-custom-btn",
            text: "切换",
        });
        customBtn.addEventListener("click", async () => {
            const name = (inputEl as HTMLInputElement).value.trim();
            if (name) {
                await this.handleCloudModelSwitch(name);
            }
        });
    }

    /**
     * 切换云端模型（使用当前激活的 API Profile）
     */
    private async handleCloudModelSwitch(modelName: string) {
        const activeProfile = this.settings.apiProfiles.find(p => p.isActive);
        if (!activeProfile || !activeProfile.apiKey) {
            new Notice("请先在设置中配置云端 API Key");
            return;
        }

        try {
            // 1. 同步 API 配置到后端
            await this.backendClient.updateConfig({
                llm_base_url: activeProfile.baseUrl,
                llm_api_key: activeProfile.apiKey,
                llm_model: modelName,
            });

            // 2. 切换模型
            const result = await this.backendClient.switchModel("llm", modelName);
            if (result.status === "ok") {
                this.settings.llmModel = modelName;
                this.currentLLM = modelName;
                await this.plugin.saveSettings();
                new Notice(`已切换为云端模型 ${modelName}`);
                await this.render();
            } else {
                new Notice(`切换失败：${result.message}`);
            }
        } catch (e) {
            new Notice("切换模型失败，请确认后端是否运行");
            console.error("[ZhiXue] 切换云端模型失败:", e);
        }
    }

    private filterModels(modelType: "llm" | "embedding"): OllamaModel[] {
        // 简单启发式：embedding 模型名通常包含 embed/text-embedding
        if (modelType === "embedding") {
            return this.models.filter(m =>
                m.name.includes("embed") || m.name.includes("e5") || m.name.includes("bge")
            );
        }
        // LLM：排除 embedding 模型
        return this.models.filter(m =>
            !m.name.includes("embed") && !m.name.includes("e5") && !m.name.includes("bge")
        );
    }

    private async handleSwitch(modelType: "llm" | "embedding", modelName: string) {
        // Embedding 切换需要确认
        if (modelType === "embedding") {
            const confirmed = await this.confirmEmbeddingSwitch(modelName);
            if (!confirmed) return;
        }

        try {
            const result = await this.backendClient.switchModel(
                modelType,
                modelName,
                modelType === "embedding" ? 768 : undefined
            );

            if (result.status === "ok") {
                // 同步更新插件设置
                if (modelType === "llm") {
                    this.settings.llmModel = modelName;
                    this.currentLLM = modelName;
                } else {
                    this.settings.embeddingModel = modelName;
                    this.currentEmbedding = modelName;
                }
                await this.plugin.saveSettings();

                new Notice(result.message);
                await this.render();
            } else {
                new Notice(`切换失败：${result.message}`);
            }
        } catch (e) {
            new Notice("切换模型失败，请确认后端是否运行");
            console.error("[ZhiXue] 切换模型失败:", e);
        }
    }

    private confirmEmbeddingSwitch(modelName: string): Promise<boolean> {
        return new Promise((resolve) => {
            const modal = new Modal(this.app);
            modal.titleEl.setText("⚠️ 切换 Embedding 模型");
            modal.contentEl.createDiv({
                text: `即将将 Embedding 模型切换为「${modelName}」。`,
            });
            modal.contentEl.createDiv({
                cls: "zhixue-modal-warning",
                text: "⚠️ 注意：切换后向量维度可能不兼容，建议重新索引知识库以获得最佳效果。",
            });

            const btnContainer = modal.contentEl.createDiv({ cls: "zhixue-modal-btns" });
            btnContainer.createEl("button", { text: "取消" }).addEventListener("click", () => {
                modal.close();
                resolve(false);
            });
            btnContainer.createEl("button", { text: "确认切换", cls: "mod-cta" }).addEventListener("click", () => {
                modal.close();
                resolve(true);
            });

            modal.open();
        });
    }

    private renderConnectionConfig(parent: HTMLElement) {
        const sectionEl = parent.createDiv({ cls: "zhixue-model-section" });

        const sectionHeader = sectionEl.createDiv({ cls: "zhixue-model-section-header" });
        sectionHeader.createSpan({ cls: "zhixue-model-section-title", text: "🔗 连接配置" });

        // Ollama 地址
        const urlRow = sectionEl.createDiv({ cls: "zhixue-config-row" });
        urlRow.createSpan({ cls: "zhixue-config-label", text: "Ollama 地址" });
        const urlInput = urlRow.createEl("input", {
            cls: "zhixue-config-input",
            attr: { type: "text", value: this.settings.ollamaUrl },
        });
        const urlSaveBtn = urlRow.createEl("button", { cls: "zhixue-config-save-btn", text: "保存" });
        urlSaveBtn.addEventListener("click", async () => {
            const val = (urlInput as HTMLInputElement).value.trim();
            if (val) {
                this.settings.ollamaUrl = val;
                await this.plugin.saveSettings();
                try {
                    await this.backendClient.updateConfig({ ollama_base_url: val });
                    new Notice("Ollama 地址已更新");
                } catch {
                    new Notice("保存失败，后端未运行");
                }
            }
        });

        // API Key
        const keyRow = sectionEl.createDiv({ cls: "zhixue-config-row" });
        keyRow.createSpan({ cls: "zhixue-config-label", text: "API Key" });
        const keyInput = keyRow.createEl("input", {
            cls: "zhixue-config-input",
            attr: { type: "password", value: this.settings.ollamaApiKey || "ollama" },
        });
        const keySaveBtn = keyRow.createEl("button", { cls: "zhixue-config-save-btn", text: "保存" });
        keySaveBtn.addEventListener("click", async () => {
            const val = (keyInput as HTMLInputElement).value.trim();
            if (val) {
                this.settings.ollamaApiKey = val;
                await this.plugin.saveSettings();
                try {
                    await this.backendClient.updateConfig({ ollama_api_key: val });
                    new Notice("API Key 已更新");
                } catch {
                    new Notice("保存失败，后端未运行");
                }
            }
        });
        keyRow.createEl("span", { cls: "zhixue-config-hint", text: "本地 Ollama 无需修改" });
    }

    private async refreshModels() {
        this.isLoading = true;
        this._hasRefreshed = true;
        await this.render();

        try {
            const data = await this.backendClient.listModels();
            this.ollamaRunning = data.ollama_running;
            this.models = data.models || [];
            this.currentLLM = data.current_llm || this.settings.llmModel;
            this.currentEmbedding = data.current_embedding || this.settings.embeddingModel;
        } catch (e) {
            this.ollamaRunning = false;
            this.models = [];
            this.currentLLM = this.settings.llmModel;
            this.currentEmbedding = this.settings.embeddingModel;
            console.error("[ZhiXue] 获取 Ollama 模型列表失败:", e);
        } finally {
            this.isLoading = false;
            await this.render();
        }
    }
}
