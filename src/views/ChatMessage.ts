/**
 * 智学 (ZhiXue) - 聊天消息组件
 */

import { Component, MarkdownRenderer } from "obsidian";
import type { ChatMessage } from "../utils/constants";

export class ChatMessageComponent extends Component {
    private containerEl: HTMLElement;
    private message: ChatMessage;
    private aiName: string;
    private app: any;
    private onOpenNote?: (source: string) => void;

    constructor(
        containerEl: HTMLElement,
        message: ChatMessage,
        aiName: string = "小智",
        onOpenNote?: (source: string) => void,
        app?: any
    ) {
        super();
        this.containerEl = containerEl;
        this.message = message;
        this.aiName = aiName;
        this.onOpenNote = onOpenNote;
        this.app = app;
    }

    onload() {
        this.render();
    }

    private render() {
        const { role, content, sources } = this.message;
        const isUser = role === "user";

        const msgEl = this.containerEl.createDiv({
            cls: `zhixue-chat-message zhixue-chat-${isUser ? "user" : "assistant"}`,
        });

        // 头像 + 名称
        const headerEl = msgEl.createDiv({ cls: "zhixue-chat-message-header" });
        headerEl.createSpan({
            cls: "zhixue-chat-avatar",
            text: isUser ? "👤" : "🤖",
        });
        headerEl.createSpan({
            cls: "zhixue-chat-name",
            text: isUser ? "你" : this.aiName,
        });

        // 消息内容
        const bodyEl = msgEl.createDiv({ cls: "zhixue-chat-message-body" });
        if (isUser) {
            bodyEl.textContent = content;
        } else {
            // AI 回复使用 Markdown 渲染
            MarkdownRenderer.render(this.app, content, bodyEl, "", this);
        }

        // 来源引用
        if (!isUser && sources && sources.length > 0) {
            const sourcesEl = msgEl.createDiv({ cls: "zhixue-chat-sources" });
            sourcesEl.createSpan({ text: "📎 来源：", cls: "zhixue-sources-label" });
            sources.forEach((source) => {
                const name = source.split("/").pop()?.replace(".md", "") || source;
                const link = sourcesEl.createEl("a", {
                    cls: "zhixue-source-link",
                    text: name,
                    attr: { href: "#", title: source },
                });
                link.addEventListener("click", (e) => {
                    e.preventDefault();
                    if (this.onOpenNote) {
                        this.onOpenNote(source);
                    }
                });
            });
        }
    }
}
