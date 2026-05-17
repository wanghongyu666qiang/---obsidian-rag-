/**
 * 智学 (ZhiXue) - 对话存储服务
 * 将对话保存为 Vault 中的 Markdown 文件
 */

import { App, TFile, Notice } from "obsidian";
import { formatConversationMarkdown, getConversationFileName } from "../utils/formatter";
import { ZHIXUE_DIR, CONVERSATIONS_DIR, type ChatMessage } from "../utils/constants";

export class ConversationStore {
    private app: App;
    private basePath: string;

    constructor(app: App, conversationPath: string = "_zhixue/conversations") {
        this.app = app;
        this.basePath = conversationPath;
    }

    /**
     * 保存对话为 Markdown 文件
     */
    async saveConversation(messages: ChatMessage[], aiName: string = "小智"): Promise<string | null> {
        if (messages.length === 0) return null;

        try {
            // 确保目录存在
            const dirExists = await this.app.vault.adapter.exists(this.basePath);
            if (!dirExists) {
                await this.app.vault.createFolder(this.basePath);
            }

            // 生成文件内容
            const content = formatConversationMarkdown(messages, aiName);
            const fileName = getConversationFileName();
            const filePath = `${this.basePath}/${fileName}`;

            // 写入文件
            await this.app.vault.create(filePath, content);

            return filePath;
        } catch (error) {
            console.error("[ZhiXue] 保存对话失败:", error);
            new Notice("智学：保存对话失败");
            return null;
        }
    }

    /**
     * 列出所有历史对话
     */
    async listConversations(): Promise<Array<{ path: string; name: string; created: string }>> {
        try {
            const dirExists = await this.app.vault.adapter.exists(this.basePath);
            if (!dirExists) return [];

            const files = await this.app.vault.adapter.list(this.basePath);
            return files.files
                .filter((f: string) => f.endsWith(".md"))
                .map((f: string) => {
                    const name = f.split("/").pop()?.replace(".md", "") || "";
                    return {
                        path: f,
                        name,
                        created: name, // 文件名即包含时间戳
                    };
                })
                .sort((a: any, b: any) => b.created.localeCompare(a.created));
        } catch {
            return [];
        }
    }

    /**
     * 加载历史对话
     */
    async loadConversation(path: string): Promise<ChatMessage[]> {
        try {
            const file = this.app.vault.getAbstractFileByPath(path);
            if (!file || !(file instanceof TFile)) return [];

            const content = await this.app.vault.read(file);
            return this.parseConversationContent(content);
        } catch {
            return [];
        }
    }

    /**
     * 解析对话 Markdown 内容
     */
    private parseConversationContent(content: string): ChatMessage[] {
        const messages: ChatMessage[] = [];
        const lines = content.split("\n");
        let currentRole: "user" | "assistant" | null = null;
        let currentContent: string[] = [];

        for (const line of lines) {
            if (line.startsWith("## 🤖")) {
                if (currentRole && currentContent.length > 0) {
                    messages.push({
                        role: currentRole,
                        content: currentContent.join("\n").trim(),
                        timestamp: new Date().toISOString(),
                    });
                }
                currentRole = "assistant";
                currentContent = [];
            } else if (line.startsWith("## 👤")) {
                if (currentRole && currentContent.length > 0) {
                    messages.push({
                        role: currentRole,
                        content: currentContent.join("\n").trim(),
                        timestamp: new Date().toISOString(),
                    });
                }
                currentRole = "user";
                currentContent = [];
            } else if (currentRole && !line.startsWith("---") && !line.startsWith("# ") && !line.startsWith("type:")) {
                currentContent.push(line);
            }
        }

        // 最后一轮
        if (currentRole && currentContent.length > 0) {
            messages.push({
                role: currentRole,
                content: currentContent.join("\n").trim(),
                timestamp: new Date().toISOString(),
            });
        }

        return messages;
    }

    /**
     * 更新基础路径
     */
    updatePath(path: string) {
        this.basePath = path;
    }
}
