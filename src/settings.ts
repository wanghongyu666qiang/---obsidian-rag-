/**
 * 智学 (ZhiXue) - 设置面板
 * 完全可视化，小白友好
 */

import { App, PluginSettingTab, Setting, Notice, Modal, TextComponent } from "obsidian";
import type ZhiXuePlugin from "./main";
import { DEFAULT_SETTINGS, type ZhiXueSettings, type ApiProfile } from "./utils/constants";

export class ZhiXueSettingTab extends PluginSettingTab {
    private plugin: ZhiXuePlugin;

    constructor(app: App, plugin: ZhiXuePlugin) {
        super(app, plugin);
        this.plugin = plugin;
    }

    display(): void {
        const { containerEl } = this;
        containerEl.empty();

        containerEl.createEl("h1", { text: "🔧 智学设置" });

        // === 基础配置 ===
        new Setting(containerEl).setHeading().setName("基础配置");

        new Setting(containerEl)
            .setName("后端端口")
            .setDesc("Python 后端服务端口")
            .addText((text) =>
                text.setValue(String(this.plugin.settings.backendPort)).onChange(async (value) => {
                    const port = parseInt(value);
                    if (!isNaN(port) && port > 0 && port < 65536) {
                        this.plugin.settings.backendPort = port;
                        await this.plugin.saveSettings();
                    }
                })
            );

        new Setting(containerEl)
            .setName("Python 路径")
            .setDesc("Python 可执行文件完整路径（留空则自动查找）")
            .addText((text) =>
                text.setValue(this.plugin.settings.pythonPath).onChange(async (value) => {
                    this.plugin.settings.pythonPath = value.trim();
                    await this.plugin.saveSettings();
                })
            );

        new Setting(containerEl)
            .setName("自动启动后端")
            .setDesc("打开 Obsidian 时自动启动 Python 后端")
            .addToggle((toggle) =>
                toggle.setValue(this.plugin.settings.autoStartBackend).onChange(async (value) => {
                    this.plugin.settings.autoStartBackend = value;
                    await this.plugin.saveSettings();
                })
            );

        // === LLM API 配置（多 Profile 管理）===
        new Setting(containerEl).setHeading().setName("LLM API 配置");

        // 显示当前激活的 Profile
        const activeProfile = this.plugin.settings.apiProfiles.find(p => p.isActive);
        new Setting(containerEl)
            .setName("当前激活")
            .setDesc(activeProfile
                ? `${activeProfile.name}（${activeProfile.baseUrl}）`
                : "未配置云端 API，将使用本地 Ollama");

        // 添加配置按钮
        new Setting(containerEl)
            .setName("添加 API 配置")
            .setDesc("添加新的 API Key 配置（如硅基流动、OpenAI 等），添加后自动激活并立即生效")
            .addButton(btn =>
                btn.setButtonText("添加").onClick(() => {
                    new ApiProfileModal(this.app, this.plugin, () => this.display()).open();
                })
            );

        // 列出所有已配置的 Profile
        if (this.plugin.settings.apiProfiles.length === 0) {
            new Setting(containerEl)
                .setName("暂无配置")
                .setDesc("点击上方「添加」按钮添加你的第一个 API 配置");
        } else {
            this.plugin.settings.apiProfiles.forEach(profile => {
                const maskedKey = profile.apiKey
                    ? "*".repeat(Math.max(0, profile.apiKey.length - 4)) + profile.apiKey.slice(-4)
                    : "(未填写)";
                new Setting(containerEl)
                    .setName(profile.isActive ? `✅ ${profile.name}` : profile.name)
                    .setDesc(`${profile.baseUrl}  |  Key: ${maskedKey}`)
                    .addButton(btn => {
                        if (profile.isActive) {
                            btn.setButtonText("激活中").setDisabled(true);
                        } else {
                            btn.setButtonText("激活").onClick(async () => {
                                await this.activateProfile(profile.id);
                            });
                        }
                    })
                    .addButton(btn =>
                        btn.setButtonText("编辑").onClick(() => {
                            new ApiProfileModal(this.app, this.plugin, () => this.display(), profile).open();
                        })
                    )
                    .addButton(btn =>
                        btn.setButtonText("删除").setWarning().onClick(async () => {
                            await this.deleteProfile(profile.id);
                        })
                    );
            });
        }

        // 模型管理（快速切换模型）
        new Setting(containerEl)
            .setName("模型管理")
            .setDesc(`当前 LLM: ${this.plugin.settings.llmModel} | Embedding: ${this.plugin.settings.embeddingModel}`)
            .addButton((btn) =>
                btn.setButtonText("模型管理").onClick(() => {
                    this.plugin.activateModelSwitch();
                })
            );

        // === Embedding / Ollama 配置 ===
        new Setting(containerEl).setHeading().setName("Embedding (向量模型)");

        new Setting(containerEl)
            .setName("Ollama 地址")
            .setDesc("本地 Ollama 服务地址，同时用于 Embedding 向量化")
            .addText((text) =>
                text.setValue(this.plugin.settings.ollamaUrl).onChange(async (value) => {
                    this.plugin.settings.ollamaUrl = value;
                    await this.plugin.saveSettings();
                })
            );

        const apiKeySetting = new Setting(containerEl)
            .setName("Ollama API Key")
            .setDesc("本地 Ollama 通常为 ollama，无需修改")
            .addText((text) => {
                text.setValue(this.plugin.settings.ollamaApiKey || "")
                    .onChange(async (value) => {
                        this.plugin.settings.ollamaApiKey = value;
                        await this.plugin.saveSettings();
                    });
                text.inputEl.type = "password";
                text.inputEl.addEventListener("blur", () => {
                    this.plugin.syncSettingsToBackend();
                });
            });
        apiKeySetting.settingEl.setAttribute("data-id", "api-key");

        // === Embedding 云端 API 配置 ===
        new Setting(containerEl).setHeading().setName("Embedding 云端 API");

        new Setting(containerEl)
            .setName("Embedding 来源")
            .setDesc("选择向量化模型来源：本地 Ollama 或云端 API（如 SiliconFlow）")
            .addDropdown(dropdown =>
                dropdown
                    .addOption("ollama", "本地 Ollama（默认）")
                    .addOption("cloud", "云端 API")
                    .setValue(this.plugin.settings.embeddingSource)
                    .onChange(async (value: "ollama" | "cloud") => {
                        this.plugin.settings.embeddingSource = value;
                        await this.plugin.saveSettings();
                        this.display(); // 刷新界面
                    })
            );

        if (this.plugin.settings.embeddingSource === "cloud") {
            new Setting(containerEl)
                .setName("Embedding API 地址")
                .setDesc("云端 Embedding API 地址，如：https://api.siliconflow.cn/v1")
                .addText(text =>
                    text.setValue(this.plugin.settings.embeddingBaseUrl).onChange(async (value) => {
                        this.plugin.settings.embeddingBaseUrl = value.trim();
                        await this.plugin.saveSettings();
                    })
                );

            new Setting(containerEl)
                .setName("Embedding API Key")
                .setDesc("云端 Embedding 服务的 API Key")
                .addText(text => {
                    text.setValue(this.plugin.settings.embeddingApiKey).onChange(async (value) => {
                        this.plugin.settings.embeddingApiKey = value.trim();
                        await this.plugin.saveSettings();
                    });
                    text.inputEl.type = "password";
                });

            new Setting(containerEl)
                .setName("应用 Embedding 配置")
                .setDesc("保存后将 Embedding 切换到云端 API，并自动重新索引")
                .addButton(btn =>
                    btn.setButtonText("应用并同步到后端").setCta().onClick(async () => {
                        await this.plugin.syncSettingsToBackend();
                        new Notice("✅ Embedding 配置已同步到后端");
                    })
                );
        }

        // === AI 印象 ===
        new Setting(containerEl).setHeading().setName("AI 印象");

        new Setting(containerEl)
            .setName("AI 名字")
            .setDesc("你的 AI 助手的名字")
            .addText((text) =>
                text.setValue(this.plugin.settings.aiName).onChange(async (value) => {
                    this.plugin.settings.aiName = value;
                    await this.plugin.saveSettings();
                })
            );

        new Setting(containerEl)
            .setName("编辑 AI 印象文件")
            .setDesc("在 Obsidian 中编辑 AI 的人格、记忆和对你的理解")
            .addButton((btn) =>
                btn.setButtonText("打开 AI 印象").onClick(() => {
                    this.app.workspace.openLinkText("_zhixue/ai-profile.md", "", false);
                })
            );

        // === 使用习惯 ===
        new Setting(containerEl).setHeading().setName("使用习惯");

        const habitStats = this.createHabitStatsEl(containerEl);

        new Setting(containerEl)
            .setName("查看详细习惯")
            .setDesc("查看 AI 对你使用习惯的理解")
            .addButton((btn) =>
                btn.setButtonText("打开习惯数据").onClick(() => {
                    this.app.workspace.openLinkText("_zhixue/habits.json", "", false);
                })
            );

        // === 对话存储 ===
        new Setting(containerEl).setHeading().setName("对话存储");

        new Setting(containerEl)
            .setName("自动保存对话")
            .setDesc("每次对话结束后自动保存为 Markdown 文件")
            .addToggle((toggle) =>
                toggle.setValue(this.plugin.settings.autoSaveConversation).onChange(async (value) => {
                    this.plugin.settings.autoSaveConversation = value;
                    await this.plugin.saveSettings();
                })
            );

        new Setting(containerEl)
            .setName("存储路径")
            .setDesc("对话文件保存的 Vault 路径")
            .addText((text) =>
                text.setValue(this.plugin.settings.conversationPath).onChange(async (value) => {
                    this.plugin.settings.conversationPath = value;
                    await this.plugin.saveSettings();
                })
            );

        new Setting(containerEl)
            .setName("打开对话目录")
            .addButton((btn) =>
                btn.setButtonText("打开").onClick(() => {
                    this.app.workspace.openLinkText("_zhixue/conversations", "", false);
                })
            );

        // === Homepage 设置 ===
        new Setting(containerEl).setHeading().setName("Homepage");

        new Setting(containerEl)
            .setName("首页模式")
            .setDesc("选择智学首页的展示方式")
            .addDropdown((dropdown) =>
                dropdown
                    .addOption("sidebar", "侧边栏模式")
                    .addOption("dashboard", "全屏 Dashboard 模式")
                    .setValue(this.plugin.settings.homepageMode)
                    .onChange(async (value: "sidebar" | "dashboard") => {
                        this.plugin.settings.homepageMode = value;
                        await this.plugin.saveSettings();
                    })
            );

        new Setting(containerEl)
            .setName("设为 Homepage")
            .setDesc("将智学设为 Obsidian 打开时的首页（需安装 Homepage 插件）")
            .addButton((btn) =>
                btn.setButtonText("设为首页").onClick(() => {
                    this.setAsHomepage();
                })
            );

        // === 索引管理 ===
        new Setting(containerEl).setHeading().setName("索引管理");

        new Setting(containerEl)
            .setName("重新索引全部")
            .setDesc("重新摄取 Vault 中的所有笔记到 RAG 知识库")
            .addButton((btn) =>
                btn.setButtonText("重新索引").onClick(async () => {
                    new Notice("智学：开始重新索引...");
                    btn.setButtonText("索引中...");
                    btn.setDisabled(true);
                    const intervalId = window.setInterval(async () => {
                        try {
                            const status = await this.plugin.backendClient.getIngestStatus();
                            if (status.ingest_progress) {
                                const p = status.ingest_progress;
                                if (p.status === "done" || p.status === "error") {
                                    window.clearInterval(intervalId);
                                    btn.setButtonText("重新索引");
                                    btn.setDisabled(false);
                                    new Notice(`智学：索引完成，处理了 ${p.processed}/${p.total} 个文件`);
                                }
                            }
                        } catch {
                            // 忽略轮询错误
                        }
                    }, 2000);
                    try {
                        const result = await this.plugin.backendClient.ingestVault(true);
                        window.clearInterval(intervalId);
                        btn.setButtonText("重新索引");
                        btn.setDisabled(false);
                        new Notice(`智学：索引完成，处理了 ${result.files_processed} 个文件`);
                    } catch {
                        window.clearInterval(intervalId);
                        btn.setButtonText("重新索引");
                        btn.setDisabled(false);
                        new Notice("智学：索引失败，请确认后端是否运行");
                    }
                })
            );

        new Setting(containerEl)
            .setName("仅索引新增")
            .setDesc("仅摄取新增或修改的笔记")
            .addButton((btn) =>
                btn.setButtonText("增量索引").onClick(async () => {
                    btn.setButtonText("索引中...");
                    btn.setDisabled(true);
                    const intervalId = window.setInterval(async () => {
                        try {
                            const status = await this.plugin.backendClient.getIngestStatus();
                            if (status.ingest_progress) {
                                const p = status.ingest_progress;
                                if (p.status === "done" || p.status === "error") {
                                    window.clearInterval(intervalId);
                                    btn.setButtonText("增量索引");
                                    btn.setDisabled(false);
                                    new Notice(`智学：增量索引完成，处理了 ${p.processed}/${p.total} 个文件`);
                                }
                            }
                        } catch {
                            // ignore
                        }
                    }, 2000);
                    try {
                        const result = await this.plugin.backendClient.ingestVault(false);
                        window.clearInterval(intervalId);
                        btn.setButtonText("增量索引");
                        btn.setDisabled(false);
                        new Notice(`智学：增量索引完成，处理了 ${result.files_processed} 个文件`);
                    } catch {
                        window.clearInterval(intervalId);
                        btn.setButtonText("增量索引");
                        btn.setDisabled(false);
                        new Notice("智学：索引失败");
                    }
                })
            );
    }

    // === 激活 / 删除 Profile ===

    async activateProfile(profileId: string): Promise<void> {
        this.plugin.settings.apiProfiles.forEach(p => {
            p.isActive = (p.id === profileId);
        });
        await this.plugin.saveSettings();
        await this.plugin.syncSettingsToBackend();
        new Notice("智学：已切换 API 配置并同步到后端");
        this.display();
    }

    async deleteProfile(profileId: string): Promise<void> {
        const idx = this.plugin.settings.apiProfiles.findIndex(p => p.id === profileId);
        if (idx === -1) return;
        const wasActive = this.plugin.settings.apiProfiles[idx].isActive;
        this.plugin.settings.apiProfiles.splice(idx, 1);
        // 如果删的是激活的，且还有剩余，激活第一个
        if (wasActive && this.plugin.settings.apiProfiles.length > 0) {
            this.plugin.settings.apiProfiles[0].isActive = true;
        }
        await this.plugin.saveSettings();
        await this.plugin.syncSettingsToBackend();
        new Notice("智学：已删除并同步到后端");
        this.display();
    }

    private createHabitStatsEl(containerEl: HTMLElement): HTMLElement {
        const el = containerEl.createDiv({ cls: "zhixue-habit-stats" });

        this.plugin.backendClient.getHabits().then((data) => {
            el.createSpan({ text: `总查询次数：${data.total_queries || 0}` });

            const topics = Object.entries(data.topics || {});
            if (topics.length > 0) {
                const topTopics = topics
                    .sort(([, a]: any, [, b]: any) => b.count - a.count)
                    .slice(0, 5)
                    .map(([name]) => name)
                    .join("、");
                el.createSpan({ text: ` | 高频主题：${topTopics}` });
            }
        }).catch(() => {
            el.createSpan({ text: "后端未就绪" });
        });

        return el;
    }

    private setAsHomepage() {
        // @ts-ignore - 访问其他插件的配置
        const homepagePlugin = this.app.plugins?.plugins?.["homepage"];
        if (homepagePlugin) {
            const mode = this.plugin.settings.homepageMode;
            const viewType = mode === "dashboard" ? "zhixue-dashboard" : "zhixue-chat";
            homepagePlugin.settings.homepage = viewType;
            homepagePlugin.saveSettings();
            new Notice("智学：已设为 Homepage！重新打开 Obsidian 生效。");
        } else {
            new Notice("智学：请先安装 Homepage 插件");
        }
    }
}

// === API Profile 编辑弹窗 ===

class ApiProfileModal extends Modal {
    private plugin: ZhiXuePlugin;
    private onSave: () => void;
    private existingProfile?: ApiProfile;
    private nameInput!: TextComponent;
    private urlInput!: TextComponent;
    private keyInput!: TextComponent;

    constructor(app: App, plugin: ZhiXuePlugin, onSave: () => void, profile?: ApiProfile) {
        super(app);
        this.plugin = plugin;
        this.onSave = onSave;
        this.existingProfile = profile;
    }

    onOpen() {
        const { contentEl } = this;
        contentEl.empty();
        contentEl.createEl("h2", {
            text: this.existingProfile ? "编辑 API 配置" : "添加 API 配置",
        });

        // 配置名称
        new Setting(contentEl)
            .setName("配置名称")
            .setDesc("给你这个 API Key 起个名字，方便识别")
            .addText(text => {
                this.nameInput = text;
                text.setValue(this.existingProfile?.name || "")
                    .setPlaceholder("例如：硅基流动-免费");
            });

        // API 地址
        new Setting(contentEl)
            .setName("API 地址")
            .setDesc("大语言模型 API 地址，例如：https://api.siliconflow.cn/v1")
            .addText(text => {
                this.urlInput = text;
                text.setValue(this.existingProfile?.baseUrl || "")
                    .setPlaceholder("https://api.siliconflow.cn/v1");
            });

        // API Key
        new Setting(contentEl)
            .setName("API Key")
            .setDesc("你的 API Key（填写后自动激活并立即生效）")
            .addText(text => {
                this.keyInput = text;
                text.setValue(this.existingProfile?.apiKey || "")
                    .setPlaceholder("sk-...");
                text.inputEl.type = "password";
            });

        // 保存按钮
        new Setting(contentEl)
            .addButton(btn => {
                btn.setButtonText(this.existingProfile ? "保存" : "添加并激活")
                    .setCta()
                    .onClick(async () => {
                        const name = this.nameInput.getValue().trim();
                        const baseUrl = this.urlInput.getValue().trim();
                        const apiKey = this.keyInput.getValue().trim();

                        if (!name) { new Notice("请填写配置名称"); return; }
                        if (!baseUrl) { new Notice("请填写 API 地址"); return; }
                        if (!apiKey) { new Notice("请填写 API Key"); return; }

                        if (this.existingProfile) {
                            // 编辑现有
                            this.existingProfile.name = name;
                            this.existingProfile.baseUrl = baseUrl;
                            this.existingProfile.apiKey = apiKey;
                        } else {
                            // 新增：先取消其他激活状态
                            this.plugin.settings.apiProfiles.forEach(p => p.isActive = false);
                            this.plugin.settings.apiProfiles.push({
                                id: Date.now().toString(36) + Math.random().toString(36).slice(2, 8),
                                name,
                                baseUrl,
                                apiKey,
                                isActive: true,
                            });
                        }

                        await this.plugin.saveSettings();
                        await this.plugin.syncSettingsToBackend();
                        new Notice(`智学：${name} 已保存并立即生效 ✓`);
                        this.onSave();
                        this.close();
                    });
            })
            .addButton(btn => {
                btn.setButtonText("取消").onClick(() => this.close());
            });
    }

    onClose() {
        this.contentEl.empty();
    }
}
