/**
 * 智学 (ZhiXue) - Homepage Dashboard 全屏视图
 * 打开 Obsidian 就看到 AI 助手 + 最近笔记 + 推荐
 */

import { ItemView, WorkspaceLeaf, Notice, MarkdownView, MarkdownRenderer, Component } from "obsidian";
import { DASHBOARD_VIEW_TYPE, type ZhiXueSettings, type ChatMessage } from "../utils/constants";
import { BackendClient } from "../services/BackendClient";
import { ConversationStore } from "../services/ConversationStore";

export class DashboardView extends ItemView {
    private settings: ZhiXueSettings;
    private backendClient: BackendClient;
    private conversationStore: ConversationStore;
    private messages: ChatMessage[] = [];
    private messagesContainer!: HTMLElement;
    private inputEl!: HTMLTextAreaElement;
    private isLoading = false;

    constructor(
        leaf: WorkspaceLeaf,
        settings: ZhiXueSettings,
        backendClient: BackendClient,
        conversationStore: ConversationStore
    ) {
        super(leaf);
        this.settings = settings;
        this.backendClient = backendClient;
        this.conversationStore = conversationStore;
    }

    getViewType() {
        return DASHBOARD_VIEW_TYPE;
    }

    getDisplayText() {
        return "智学首页";
    }

    getIcon() {
        return "sparkles";
    }

    async onOpen() {
        this.containerEl.empty();
        this.containerEl.addClasses(["zhixue-dashboard"]);

        // === 顶部问候栏 ===
        const heroEl = this.containerEl.createDiv({ cls: "zhixue-dashboard-hero" });
        const greeting = this.getGreeting();
        heroEl.createEl("h1", { text: `${greeting}，我是${this.settings.aiName} 👋` });
        heroEl.createEl("p", { text: "今天想学点什么？", cls: "zhixue-dashboard-subtitle" });

        // === 中间内容区 ===
        const contentEl = this.containerEl.createDiv({ cls: "zhixue-dashboard-content" });

        // 左侧：最近笔记 + AI推荐
        const leftPanel = contentEl.createDiv({ cls: "zhixue-dashboard-left" });

        // 最近笔记
        const recentEl = leftPanel.createDiv({ cls: "zhixue-dashboard-section" });
        recentEl.createEl("h3", { text: "📌 最近笔记" });
        const recentList = recentEl.createDiv({ cls: "zhixue-dashboard-list" });
        await this.renderRecentNotes(recentList);

        // AI 推荐
        const recommendEl = leftPanel.createDiv({ cls: "zhixue-dashboard-section" });
        recommendEl.createEl("h3", { text: "🔗 AI 推荐" });
        const recommendList = recommendEl.createDiv({ cls: "zhixue-dashboard-list" });
        await this.renderRecommendations(recommendList);

        // 右侧：聊天区域
        const rightPanel = contentEl.createDiv({ cls: "zhixue-dashboard-right" });

        // 对话区域
        this.messagesContainer = rightPanel.createDiv({
            cls: "zhixue-chat-messages",
        });
        this.addAssistantMessage(`你好！我是${this.settings.aiName}，有什么可以帮你的吗？`);

        // 快捷操作
        const quickActionsEl = rightPanel.createDiv({ cls: "zhixue-quick-actions" });
        this.createQuickAction("🔍 解释选中", quickActionsEl);
        this.createQuickAction("🔗 找关联", quickActionsEl);
        this.createQuickAction("📝 总结笔记", quickActionsEl);
        this.createQuickAction("❓ 深度提问", quickActionsEl);

        // 输入框
        const inputContainer = rightPanel.createDiv({ cls: "zhixue-chat-input-container" });
        this.inputEl = inputContainer.createEl("textarea", {
            cls: "zhixue-chat-input",
            attr: { placeholder: "输入你的问题...", rows: "2" },
        });
        const sendBtn = inputContainer.createEl("button", {
            cls: "zhixue-chat-send-btn",
            text: "➤",
        });
        sendBtn.addEventListener("click", () => this.handleSend());
        this.inputEl.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                this.handleSend();
            }
        });
    }

    async onClose() {
        if (this.settings.autoSaveConversation && this.messages.length > 1) {
            await this.conversationStore.saveConversation(this.messages, this.settings.aiName);
        }
    }

    // === 渲染辅助 ===

    private async renderRecentNotes(container: HTMLElement) {
        const files = this.app.vault.getMarkdownFiles();
        const recent = files
            .sort((a, b) => (b.stat.mtime || 0) - (a.stat.mtime || 0))
            .slice(0, 5);

        if (recent.length === 0) {
            container.createEl("p", { text: "暂无笔记", cls: "zhixue-empty" });
            return;
        }

        recent.forEach((file) => {
            const item = container.createDiv({ cls: "zhixue-dashboard-note-item" });
            const link = item.createEl("a", {
                text: file.basename,
                cls: "zhixue-note-link",
                attr: { href: "#" },
            });
            link.addEventListener("click", (e) => {
                e.preventDefault();
                this.app.workspace.openLinkText(file.path, "", false);
            });
        });
    }

    private async renderRecommendations(container: HTMLElement) {
        try {
            const rec = await this.backendClient.getRecommendations();
            const notes = rec.frequent_notes || [];
            if (notes.length === 0) {
                container.createEl("p", { text: "使用后会自动推荐", cls: "zhixue-empty" });
                return;
            }
            notes.slice(0, 5).forEach((notePath: string) => {
                const name = notePath.split("/").pop()?.replace(".md", "") || notePath;
                const item = container.createDiv({ cls: "zhixue-dashboard-note-item" });
                const link = item.createEl("a", {
                    text: name,
                    cls: "zhixue-note-link",
                    attr: { href: "#" },
                });
                link.addEventListener("click", (e) => {
                    e.preventDefault();
                    this.app.workspace.openLinkText(notePath, "", false);
                });
            });
        } catch {
            container.createEl("p", { text: "后端未就绪", cls: "zhixue-empty" });
        }
    }

    private createQuickAction(label: string, container: HTMLElement) {
        const btn = container.createEl("button", {
            cls: "zhixue-quick-action-btn",
            text: label,
        });
        btn.addEventListener("click", async () => {
            const view = this.app.workspace.getActiveViewOfType(MarkdownView);
            const selection = view?.editor.getSelection().trim();
            const title = this.app.workspace.getActiveFile()?.basename || "";

            let question = "";
            if (label.includes("解释") && selection) {
                question = `请解释：${selection}`;
            } else if (label.includes("关联")) {
                question = `请找出与「${selection || title}」相关的笔记`;
            } else if (label.includes("总结")) {
                question = `请总结笔记「${title}」的内容`;
            } else if (label.includes("提问")) {
                question = `基于「${selection || title}」提出3个深入问题`;
            }

            if (question) await this.sendQuery(question);
        });
    }

    // === 发送查询 ===

    private async handleSend() {
        const question = this.inputEl.value.trim();
        if (!question || this.isLoading) return;
        this.inputEl.value = "";
        await this.sendQuery(question);
    }

    private async sendQuery(question: string) {
        if (this.isLoading) return;
        this.isLoading = true;

        this.addUserMessage(question);
        const loadingEl = this.showLoading();

        try {
            const file = this.app.workspace.getActiveFile();
            // @ts-ignore
            const basePath = this.app.vault.adapter.getBasePath();
            const currentNote = file ? `${basePath}/${file.path}` : undefined;

            // 传入对话历史
            const history = this.messages.slice(-8).map(m => ({
                role: m.role,
                content: m.content,
            }));
            const result = await this.backendClient.query(question, "hybrid", currentNote, history);
            loadingEl.remove();

            this.addAssistantMessage(result.answer, result.sources);
            this.messages.push(
                { role: "user", content: question, timestamp: new Date().toISOString() },
                { role: "assistant", content: result.answer, sources: result.sources, timestamp: new Date().toISOString() }
            );
        } catch (error) {
            loadingEl.remove();
            this.addAssistantMessage("查询出错，请确认后端和 Ollama 是否运行。");
        } finally {
            this.isLoading = false;
        }
    }

    private addUserMessage(content: string) {
        const msgEl = this.messagesContainer.createDiv({ cls: "zhixue-chat-message zhixue-chat-user" });
        msgEl.createDiv({ cls: "zhixue-chat-message-body", text: content });
        this.scrollToBottom();
    }

    private addAssistantMessage(content: string, sources?: string[]) {
        const msgEl = this.messagesContainer.createDiv({ cls: "zhixue-chat-message zhixue-chat-assistant" });
        // 使用 Obsidian MarkdownRenderer 渲染 Markdown
        const bodyEl = msgEl.createDiv({ cls: "zhixue-chat-message-body" });
        const component = new Component();
        component.load();
        MarkdownRenderer.render(this.app, content, bodyEl, "", component);

        if (sources && sources.length > 0) {
            const sourcesEl = msgEl.createDiv({ cls: "zhixue-chat-sources" });
            sourcesEl.createSpan({ text: "📎 " });
            sources.forEach((s) => {
                sourcesEl.createSpan({ text: s.split("/").pop()?.replace(".md", "") || s, cls: "zhixue-source-link" });
            });
        }
        this.scrollToBottom();
    }

    private showLoading(): HTMLElement {
        const el = this.messagesContainer.createDiv({ cls: "zhixue-loading" });
        el.createSpan({ text: "🤖 正在思考..." });
        this.scrollToBottom();
        return el;
    }

    private scrollToBottom() {
        requestAnimationFrame(() => {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        });
    }

    private getGreeting(): string {
        const hour = new Date().getHours();
        if (hour < 6) return "夜深了";
        if (hour < 12) return "早上好";
        if (hour < 18) return "下午好";
        return "晚上好";
    }
}
