/**
 * 智学 (ZhiXue) - Vault 文件监听
 * 监听文件变化，通知后端增量更新索引
 */

import { App, Plugin, TFile, TFolder, TAbstractFile } from "obsidian";
import { BackendClient } from "./BackendClient";
import { ZHIXUE_DIR } from "../utils/constants";

export class VaultWatcher {
    private app: App;
    private plugin: Plugin;
    private backendClient: BackendClient;
    private debounceTimers: Map<string, ReturnType<typeof setTimeout>> = new Map();
    private debounceDelay = 3000; // 3秒防抖

    constructor(app: App, plugin: Plugin, backendClient: BackendClient) {
        this.app = app;
        this.plugin = plugin;
        this.backendClient = backendClient;
    }

    /**
     * 注册文件监听事件
     */
    register() {
        // 文件创建
        this.plugin.registerEvent(
            this.app.vault.on("create", (file: TAbstractFile) => {
                if (this.shouldIgnore(file)) return;
                this.debounceIngest(file.path, "create");
            })
        );

        // 文件修改
        this.plugin.registerEvent(
            this.app.vault.on("modify", (file: TAbstractFile) => {
                if (this.shouldIgnore(file)) return;
                this.debounceIngest(file.path, "modify");
            })
        );

        // 文件删除
        this.plugin.registerEvent(
            this.app.vault.on("delete", (file: TAbstractFile) => {
                if (this.shouldIgnore(file)) return;
                // 删除不需要重新摄取，知识图谱中保留即可
                console.log(`[ZhiXue] 文件已删除: ${file.path}`);
            })
        );

        // 文件重命名
        this.plugin.registerEvent(
            this.app.vault.on("rename", (file: TAbstractFile, oldPath: string) => {
                if (this.shouldIgnore(file)) return;
                this.debounceIngest(file.path, "rename");
            })
        );
    }

    /**
     * 判断是否应该忽略该文件
     */
    private shouldIgnore(file: TAbstractFile): boolean {
        if (file instanceof TFolder) return true;

        // 忽略 _zhixue 目录
        if (file.path.startsWith(ZHIXUE_DIR + "/")) return true;

        // 忽略 .obsidian 目录
        if (file.path.startsWith(".obsidian/")) return true;

        // 只处理 Markdown 文件
        if (file instanceof TFile && file.extension !== "md") return true;

        return false;
    }

    /**
     * 防抖摄取
     */
    private debounceIngest(filePath: string, event: string) {
        const existing = this.debounceTimers.get(filePath);
        if (existing) clearTimeout(existing);

        const timer = setTimeout(async () => {
            this.debounceTimers.delete(filePath);
            try {
                // 获取文件的绝对路径
                // @ts-ignore - 内部 API
                const basePath = this.app.vault.adapter.getBasePath();
                const absolutePath = `${basePath}/${filePath}`;

                await this.backendClient.ingestFile(absolutePath);
                console.log(`[ZhiXue] 已索引: ${filePath} (${event})`);
            } catch (error) {
                console.error(`[ZhiXue] 索引失败: ${filePath}`, error);
            }
        }, this.debounceDelay);

        this.debounceTimers.set(filePath, timer);
    }
}
