/**
 * 智学 (ZhiXue) - 错误日志查看器
 * 显示后端进程的详细错误日志
 */

import { App, Modal } from "obsidian";

export class ErrorLogModal extends Modal {
    private logContent: string;

    constructor(app: App, logContent: string) {
        super(app);
        this.logContent = logContent;
    }

    onOpen() {
        const { contentEl } = this;
        contentEl.empty();
        contentEl.addClass("zhixue-error-log-modal");

        // 标题
        contentEl.createEl("h2", { text: "智学后端错误日志" });

        // 日志内容（可复制）
        const pre = contentEl.createEl("pre", { cls: "zhixue-error-log-content" });
        pre.createEl("code", { text: this.logContent || "（无错误日志）" });

        // 关闭按钮
        const buttonContainer = contentEl.createDiv({ cls: "zhixue-error-log-buttons" });
        buttonContainer.createEl("button", { text: "关闭", cls: "mod-cta" })
            .addEventListener("click", () => this.close());
    }

    onClose() {
        const { contentEl } = this;
        contentEl.empty();
    }
}
