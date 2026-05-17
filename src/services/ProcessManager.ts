/**
 * 智学 (ZhiXue) - Python 后端进程管理
 * 插件启动时自动拉起，关闭时自动停止
 */

import { Notice, Plugin, TFile } from "obsidian";
import type { ChildProcess } from "child_process";
import { BackendClient } from "./BackendClient";

export class ProcessManager {
    private pythonProcess: ChildProcess | null = null;
    private backendClient: BackendClient;
    private pluginDir: string;
    private port: number;
    private plugin: Plugin;
    private retryCount = 0;
    private maxRetries = 60;  // 增加到60秒（RAG引擎首次加载需要2-3分钟）
    private retryInterval = 1000;
    private stderrBuffer = "";
    private startupError = "";
    private isStarting = false;
    private startPromise: Promise<boolean> | null = null;
    private restartCount = 0;
    private maxRestarts = 3;
    private isShutdown = false; // 标记插件是否已卸载，防止自动重启

    constructor(port: number, plugin: Plugin) {
        this.port = port;
        // 自动推导插件目录：从 manifest.dir 或 vault 路径推算
        this.pluginDir = this.resolvePluginDir(plugin);
        this.plugin = plugin;
        this.backendClient = new BackendClient(port);
    }

    /**
     * 自动推导插件目录，优先 manifest.dir，回退到 vault 路径推算
     */
    private resolvePluginDir(plugin: Plugin): string {
        const fs = window.require("fs") as typeof import("fs");
        const path = window.require("path") as typeof import("path");

        const candidates: string[] = [];

        // 1. manifest.dir（Obsidian 提供的插件目录）
        if ((plugin as any).manifest?.dir) {
            candidates.push((plugin as any).manifest.dir);
        }

        // 2. 从 vault 路径推算
        try {
            const vaultPath = (plugin as any).app?.vault?.adapter?.getBasePath?.();
            if (vaultPath) {
                candidates.push(path.join(vaultPath, ".obsidian", "plugins", "zhixue"));
            }
        } catch {}

        // 3. 硬编码候选（兼容旧环境）
        candidates.push("D:\\Obsidian Vault\\.obsidian\\plugins\\zhixue");
        candidates.push("C:\\Users\\why17\\Documents\\Obsidian Vault\\.obsidian\\plugins\\zhixue");

        for (const dir of candidates) {
            if (dir && fs.existsSync(path.join(dir, "backend"))) {
                console.log("[ZhiXue] resolvePluginDir() 选中:", dir);
                return dir;
            }
        }

        // 兜底：返回第一个候选
        const fallback = candidates[0] || "";
        console.warn("[ZhiXue] 无法找到包含 backend/ 的插件目录，使用:", fallback);
        return fallback;
    }

    updatePort(port: number) {
        this.port = port;
        this.backendClient.updatePort(port);
    }

    /**
     * 启动 Python 后端（入口，管理状态）
     * 如果已在启动中，返回现有的 promise；如果已在运行，直接返回 true。
     */
    async start(): Promise<boolean> {
        if (this.isStarting && this.startPromise) {
            return this.startPromise;
        }
        if (this.isRunning) {
            return true;
        }
        this.isStarting = true;
        this.startPromise = this._doStart();
        try {
            const result = await this.startPromise;
            return result;
        } finally {
            this.isStarting = false;
        }
    }

    /**
     * 实际的启动逻辑
     */
    private async _doStart(): Promise<boolean> {
        // 保险：如果已经持有进程且确实在运行，直接返回（不重复启动）
        if (this.pythonProcess) {
            const running = this.checkProcessAlive();
            if (running) {
                console.log("[ZhiXue] 后端已在运行，跳过启动");
                return true;
            }
            // 僵尸进程，清理引用
            this.pythonProcess = null;
        }

        try {
            const path = window.require("path") as typeof import("path");
            const { spawn } = window.require("child_process") as typeof import("child_process");

            // 找到可用的 Python
            const pythonPath = this.findPython();
            console.log("[ZhiXue] 使用 Python:", pythonPath);

            // 只清理外部占用端口的进程（不清理本插件自己的）
            // 本插件自己的进程已在上面保险检查中处理
            console.log("[ZhiXue] 准备启动后端，检查端口占用...");
            await this.killProcessOnPort();
            // 等待端口释放（Windows上TIME_WAIT通常<500ms）
            await new Promise(r => setTimeout(r, 500));

            // 使用 python -m uvicorn 方式启动（Windows 下比直接运行 start.py 更可靠）
            const vaultPath = this.findVaultFromPluginDir();
            const backendDir = path.join(this.pluginDir, "backend");
            console.log("[ZhiXue] pluginDir:", this.pluginDir);
            console.log("[ZhiXue] backendDir:", backendDir);
            console.log("[ZhiXue] pythonPath:", pythonPath);

            // 检查 backend 目录是否存在
            try {
                const fs = window.require("fs") as typeof import("fs");
                if (!fs.existsSync(backendDir)) {
                    new Notice("智学：后端目录不存在，请在插件目录放置 backend/ 文件夹");
                    console.error("[ZhiXue] 后端目录不存在:", backendDir);
                    return false;
                }
            } catch (fsErr) {
                console.error("[ZhiXue] 检查后端文件失败:", fsErr);
            }

            this.stderrBuffer = "";
            this.startupError = "";

            // 设置环境变量（必须在 spawn 前准备好）
            const env = {
                ...(typeof process !== "undefined" && process.env ? process.env : {}),
                PYTHONUNBUFFERED: "1",
                PYTHONIOENCODING: "utf-8",
            };
            if (vaultPath) {
                (env as any)["ZHIXUE_VAULT_PATH"] = vaultPath;
            }
            if (this.port) {
                (env as any)["ZHIXUE_PORT"] = String(this.port);
            }

            this.pythonProcess = spawn(
                pythonPath,
                ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(this.port)],
                {
                    cwd: backendDir,
                    env,
                    stdio: ["pipe", "pipe", "pipe"],
                    windowsHide: true,
                }
            );

            this.pythonProcess.stdout?.on("data", (data: Buffer) => {
                const text = data.toString();
                console.log("[ZhiXue Backend]", text);
            });

            this.pythonProcess.stderr?.on("data", (data: Buffer) => {
                const text = data.toString();
                console.error("[ZhiXue Backend Err]", text);
                this.stderrBuffer += text;
            });

            this.pythonProcess.on("error", (err: Error) => {
                console.error("[ZhiXue] 后端进程错误:", err);
                this.startupError = err.message;
            });

            this.pythonProcess.on("close", (code: number) => {
                console.log(`[ZhiXue] 后端进程退出，代码: ${code}`);
                const wasRunning = this.pythonProcess !== null;
                this.pythonProcess = null;

                // 插件已卸载，不自动重启
                if (this.isShutdown) {
                    console.log("[ZhiXue] 插件已卸载，跳过自动重启");
                    return;
                }

                if (wasRunning && code !== 0) {
                    // 异常退出：通知用户并尝试自动重启
                    const errMsg = this.stderrBuffer ? this.stderrBuffer.slice(-500) : "";
                    let hint = "智学后端异常退出，正在自动重启...";
                    
                    // 写入错误日志
                    if (errMsg) {
                        this.writeErrorLog(errMsg);
                    }
                    
                    if (errMsg.includes("ModuleNotFoundError") || errMsg.includes("No module named")) {
                        hint = "智学后端缺少依赖，请检查 backend/requirements.txt 是否已安装";
                        new Notice(hint, 8000);
                        return; // 依赖缺失，重启也没用，直接返回
                    } else if (errMsg.includes("CUDA") || errMsg.includes("GPU") || errMsg.includes("out of memory")) {
                        hint = "智学后端因 GPU/内存不足崩溃，正在自动重启...";
                    } else if (errMsg.includes("Address already in use") || errMsg.includes("EADDRINUSE")) {
                        hint = `智学后端端口 ${this.port} 被占用，请检查是否有其他实例正在运行`;
                        new Notice(hint, 8000);
                        return;
                    }
                    
                    this.restartCount++;
                    if (this.restartCount > this.maxRestarts) {
                        new Notice(`智学后端连续崩溃 ${this.maxRestarts} 次，已停止自动重启。请检查 _zhixue/error.log`, 10000);
                        console.error("[ZhiXue] 后端连续崩溃超过最大重启次数，停止自动重启");
                        return;
                    }
                    
                    new Notice(hint + ` (${this.restartCount}/${this.maxRestarts})`, 5000);
                    console.error("[ZhiXue] 后端异常退出，准备自动重启...", errMsg.slice(-500));
                    // 延迟 3 秒后自动重启，避免快速崩溃循环
                    setTimeout(() => {
                        if (!this.pythonProcess) {
                            this.start().catch(e => {
                                console.error("[ZhiXue] 自动重启失败:", e);
                                new Notice("智学后端重启失败，请手动重启或检查日志", 8000);
                            });
                        }
                    }, 3000);
                } else if (wasRunning && code === 0) {
                    // 正常退出（用户手动停止）
                    new Notice("智学后端已停止", 3000);
                }
            });

            // 等待后端就绪
            const ready = await this.waitForServer();
            if (ready) {
                this.restartCount = 0; // 启动成功，重置重启计数器
                console.log("[ZhiXue] 后端启动成功");
                return true;
            } else {
                // 根据错误信息给出更准确的提示
                const errMsg = this.startupError || this.stderrBuffer || "";
                let hint = "智学：后端启动超时";
                if (errMsg.includes("ModuleNotFoundError") || errMsg.includes("No module named")) {
                    hint = "智学：缺少 Python 依赖，请在 backend/ 目录运行 pip install -r requirements.txt";
                } else if (errMsg.includes("ENOENT") && !this.startupError) {
                    hint = "智学：找不到 Python，请确认已安装并加入 PATH";
                } else if (errMsg.includes("Address already in use") || errMsg.includes("EADDRINUSE")) {
                    hint = `智学：端口 ${this.port} 已被占用`;
                } else if (errMsg.includes("Permission")) {
                    hint = "智学：权限不足，无法启动后端";
                }
                new Notice(hint + `\n详情见 _zhixue/error.log`);
                // 将错误日志写入文件
                this.writeErrorLog(errMsg);
                console.error("[ZhiXue] 启动失败详情:", errMsg);
                return false;
            }
        } catch (error) {
            console.error("[ZhiXue] 启动后端失败:", error);
            new Notice("智学：启动后端失败");
            return false;
        }
    }

    /**
     * 停止 Python 后端
     */
    stop() {
        this.isShutdown = true; // 标记为已卸载，阻止自动重启
        if (this.pythonProcess) {
            try {
                const platform = window.process.platform;
                if (platform === "win32") {
                    // Windows 上使用 taskkill 来终止进程树
                    try {
                        const { execSync } = window.require("child_process") as typeof import("child_process");
                        execSync(`taskkill /PID ${this.pythonProcess.pid} /T /F`, { stdio: "ignore" });
                    } catch {
                        // fallback
                        this.pythonProcess.kill();
                    }
                } else {
                    this.pythonProcess.kill("SIGTERM");
                    setTimeout(() => {
                        if (this.pythonProcess) {
                            this.pythonProcess.kill("SIGKILL");
                        }
                    }, 3000);
                }
            } catch (e) {
                console.error("[ZhiXue] 终止后端失败:", e);
            }
            this.pythonProcess = null;
        }
    }

    /**
     * 杀掉占用本插件端口的已有进程（处理后端被外部启动的情况）
     * 这样可以确保每次启动后端时都运行的是最新代码
     */
    private async killProcessOnPort(): Promise<void> {
        const platform = window.process.platform;
        try {
            const { execSync } = window.require("child_process") as typeof import("child_process");
            if (platform === "win32") {
                const result = execSync(`netstat -ano | findstr :${this.port}`, {
                    encoding: "utf-8",
                    stdio: ["pipe", "pipe", "ignore"],
                });
                const lines = result.split("\n");
                for (const line of lines) {
                    const trimmed = line.trim();
                    if (trimmed.includes("LISTENING")) {
                        const parts = trimmed.split(/\s+/);
                        const pid = parts[parts.length - 1];
                        if (pid && pid !== String(window.process.pid)) {
                            try {
                                new Notice(`智学：端口 ${this.port} 被占用，正在清理...`, 3000);
                                execSync(`taskkill /PID ${pid} /F /T`, { stdio: "ignore" });
                                console.log(`[ZhiXue] 已杀掉占用端口的进程 PID: ${pid}`);
                            } catch {
                                // 进程可能已退出，忽略错误
                            }
                        }
                    }
                }
            } else {
                const result = execSync(`lsof -ti:${this.port}`, {
                    encoding: "utf-8",
                    stdio: ["pipe", "pipe", "ignore"],
                });
                const pids = result.trim().split("\n").filter(Boolean);
                for (const pid of pids) {
                    if (pid !== String(window.process.pid)) {
                        try {
                            new Notice(`智学：端口 ${this.port} 被占用，正在清理...`, 3000);
                            execSync(`kill -9 ${pid}`, { stdio: "ignore" });
                        } catch {
                            // 忽略
                        }
                    }
                }
            }
        } catch {
            // netstat/lsof 没找到进程（端口未被占用），或执行失败 —— 这没问题
            console.log(`[ZhiXue] 端口 ${this.port} 未被占用（或清理完成）`);
        }

    }

    /**
     * 等待后端就绪
     */
    private async waitForServer(): Promise<boolean> {
        for (let i = 0; i < this.maxRetries; i++) {
            const ready = await this.backendClient.checkHealth();
            if (ready) return true;
            await new Promise((r) => setTimeout(r, this.retryInterval));
        }
        return false;
    }

    /**
     * 查找 Python 可执行文件
     * 优先扫描已知安装目录（避免 Obsidian 中 execSync 不可靠），
     * 再回退到 where 命令和硬编码路径。
     */
    private findPython(): string {
        const fs = window.require("fs") as typeof import("fs");
        const path = window.require("path") as typeof import("path");

        // 1. 优先使用用户配置的路径
        const configured = (this.plugin as any).settings?.pythonPath;
        if (configured && configured.trim()) {
            const p = configured.trim();
            if (fs.existsSync(p)) {
                console.log("[ZhiXue] 使用用户配置的 Python:", p);
                return p;
            }
        }

        // 2. 硬编码已知路径（Python312 已确认有所有依赖）
        const knownPaths = [
            "C:\\Users\\why17\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
            "C:\\Users\\why17\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
        ];
        for (const p of knownPaths) {
            if (fs.existsSync(p)) {
                console.log("[ZhiXue] 使用已知 Python 路径:", p);
                return p;
            }
        }

        // 3. 扫描 AppData/Local/Programs/Python/ 下的版本目录
        try {
            const home = window.process.env.USERPROFILE || "";
            const pythonDir = path.join(home, "AppData", "Local", "Programs", "Python");
            if (fs.existsSync(pythonDir)) {
                const entries = fs.readdirSync(pythonDir);
                const versions = entries
                    .filter(e => e.toLowerCase().startsWith("python"))
                    .sort()
                    .reverse();
                for (const ver of versions) {
                    const p = path.join(pythonDir, ver, "python.exe");
                    if (fs.existsSync(p)) {
                        console.log("[ZhiXue] 扫描到 Python:", p);
                        return p;
                    }
                }
            }
        } catch { /* 忽略 */ }

        // 4. 在 PATH 中查找（用 where 命令）
        try {
            const { execSync } = window.require("child_process") as typeof import("child_process");
            for (const cmd of ["python", "python3"]) {
                try {
                    const found = execSync(`where ${cmd}`, { encoding: "utf-8", stdio: ["pipe", "pipe", "ignore"] })
                        .trim().split("\n")[0];
                    if (found && fs.existsSync(found)) {
                        console.log("[ZhiXue] where 找到 Python:", found);
                        return found;
                    }
                } catch { /* 忽略 */ }
            }
        } catch { /* 忽略 */ }

        console.warn("[ZhiXue] 无法找到 Python 可执行文件，fallback 到 'python'");
        return "python";
    }

    /**
     * 从 pluginDir 向上推算 vault 根目录
     * pluginDir = .../.obsidian/plugins/zhixue，向上两层即为 vault 根
     */
    private findVaultFromPluginDir(): string {
        try {
            const path = window.require("path") as typeof import("path");
            // pluginDir = .../.obsidian/plugins/zhixue
            // 向上两层：.. = plugins, ../.. = .obsidian, ../../ = vault根
            return path.join(this.pluginDir, "..", "..", "..");
        } catch {
            return "";
        }
    }

    /**
     * 将错误日志写入文件
     * 使用 pluginDir 向上推算 vault 路径，避免依赖 Obsidian 内部 API
     */
    private writeErrorLog(errMsg: string): void {
        try {
            const fs = window.require("fs") as typeof import("fs");
            const path = window.require("path") as typeof import("path");
            // pluginDir 就是 .../zhixue，vault 路径需要向上两层找到 vault 根目录
            const vaultPath = this.findVaultFromPluginDir();
            const logDir = path.join(vaultPath, "_zhixue");
            const logPath = path.join(logDir, "error.log");
            
            // 确保目录存在
            if (!fs.existsSync(logDir)) {
                fs.mkdirSync(logDir, { recursive: true });
            }
            
            // 写入错误日志（追加模式）
            const logContent = `\n=== ${new Date().toISOString()} ===\n${errMsg}\n`;
            fs.appendFileSync(logPath, logContent, "utf-8");
            console.log(`[ZhiXue] 错误日志已写入: ${logPath}`);
        } catch (e) {
            console.error("[ZhiXue] 写入错误日志失败:", e);
        }
    }

    /** 是否正在启动中 */
    get starting(): boolean {
        return this.isStarting;
    }

    get isRunning(): boolean {
        return this.checkProcessAlive();
    }

    /**
     * 可靠地检查本插件持有的后端进程是否还活着
     * Windows: tasklist 输出包含 "INFO: No tasks" 表示 PID 不存在
     * Unix: kill(0) 可靠
     */
    private checkProcessAlive(): boolean {
        if (!this.pythonProcess) return false;

        try {
            const platform = window.process.platform;
            if (platform === "win32") {
                const { execSync } = window.require("child_process") as typeof import("child_process");
                const output = execSync(
                    `tasklist /FI "PID eq ${this.pythonProcess.pid}" /FO CSV`,
                    { encoding: "utf-8", stdio: ["pipe", "pipe", "ignore"] }
                );
                // PID 不存在时 tasklist 返回 0，但输出包含 "INFO: No tasks"
                if (output.includes("INFO: No tasks")) {
                    this.pythonProcess = null;
                    return false;
                }
                return true;
            } else {
                this.pythonProcess.kill(0);
                return true;
            }
        } catch {
            this.pythonProcess = null;
            return false;
        }
    }
}
