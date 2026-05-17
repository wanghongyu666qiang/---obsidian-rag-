/**
 * 智学 (ZhiXue) - Markdown 格式化工具
 */

import type { ChatMessage } from "./constants";

/**
 * 格式化对话为 Markdown
 */
export function formatConversationMarkdown(
    messages: ChatMessage[],
    aiName: string = "小智"
): string {
    const now = new Date();
    const dateStr = now.toISOString().split("T")[0];
    const timeStr = now.toTimeString().split(" ")[0].replace(/:/g, "").slice(0, 6);

    const frontmatter = `---
type: zhixue-conversation
created: ${now.toISOString()}
messages: ${messages.length}
tags: [zhixue, conversation]
---`;

    const title = `# 对话 — ${dateStr} ${now.toTimeString().slice(0, 5)}`;

    const body = messages
        .map((msg) => {
            const icon = msg.role === "assistant" ? `## 🤖 ${aiName}` : "## 👤 用户";
            let content = msg.content;

            // 添加来源引用
            if (msg.role === "assistant" && msg.sources && msg.sources.length > 0) {
                const sourceLinks = msg.sources
                    .map((s) => {
                        const name = s.split("/").pop()?.replace(".md", "") || s;
                        return `[[${name}]]`;
                    })
                    .join(" | ");
                content += `\n\n> 📎 来源：${sourceLinks}`;
            }

            return `${icon}\n${content}`;
        })
        .join("\n\n");

    return `${frontmatter}\n\n${title}\n\n${body}\n`;
}

/**
 * 生成对话文件名
 */
export function getConversationFileName(): string {
    const now = new Date();
    const dateStr = now.toISOString().split("T")[0];
    const timeStr = now.toTimeString().split(" ")[0].replace(/:/g, "");
    return `${dateStr}-${timeStr}.md`;
}
