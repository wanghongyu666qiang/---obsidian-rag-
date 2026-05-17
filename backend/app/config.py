"""
智学 (ZhiXue) 后端配置
"""
import logging
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ============================================================
#  sensible defaults：开箱即用
# ============================================================

# 1. .env 不存在时，自动从 .env.example 复制
_backend_dir = Path(__file__).parent.parent
_env_file = _backend_dir / ".env"
_env_example = _backend_dir / ".env.example"

if not _env_file.exists() and _env_example.exists():
    try:
        shutil.copy2(_env_example, _env_file)
        print(f"[ZhiXue] 已自动创建 .env 配置文件（基于 .env.example）")
    except Exception as e:
        print(f"[ZhiXue] 警告：无法复制 .env.example: {e}")

# 2. 加载 .env（override=False：让 start.py 传入的环境变量优先）
load_dotenv(override=False)
load_dotenv(_env_file, override=False)


class Settings:
    """全局配置"""

    # === 服务配置 ===
    HOST: str = os.getenv("ZHIXUE_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("ZHIXUE_PORT", "18765"))
    DEBUG: bool = os.getenv("ZHIXUE_DEBUG", "false").lower() == "true"

    # === Ollama / Embedding 配置 ===
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    OLLAMA_API_KEY: str = os.getenv("OLLAMA_API_KEY", "ollama")
    EMBEDDING_MODEL: str = os.getenv("ZHIXUE_EMBEDDING_MODEL", "")
    EMBEDDING_DIM: int = int(os.getenv("ZHIXUE_EMBEDDING_DIM", "0"))  # 为0时自动检测
    EMBEDDING_BASE_URL: str = os.getenv("ZHIXUE_EMBEDDING_BASE_URL", "")
    EMBEDDING_API_KEY: str = os.getenv("ZHIXUE_EMBEDDING_API_KEY", "")
    EMBEDDING_SOURCE: str = os.getenv("ZHIXUE_EMBEDDING_SOURCE", "ollama")  # "ollama" | "cloud"

    # === LLM 配置（可与 Embedding 使用不同的服务） ===
    LLM_MODEL: str = os.getenv("ZHIXUE_LLM_MODEL", "deepseek-r1:7b")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")   # 为空时回退到 OLLAMA_BASE_URL
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")     # 为空时回退到 OLLAMA_API_KEY

    # === Vault 配置 ===
    VAULT_PATH: str = os.getenv("ZHIXUE_VAULT_PATH", "")
    VAULT_NAME: str = os.getenv("ZHIXUE_VAULT_NAME", "")

    # === RAG 配置 ===
    WORKING_DIR: str = os.getenv("ZHIXUE_WORKING_DIR", "")
    PARSER: str = os.getenv("ZHIXUE_PARSER", "mineru")
    PARSE_METHOD: str = os.getenv("ZHIXUE_PARSE_METHOD", "auto")
    CHUNK_SIZE: int = int(os.getenv("ZHIXUE_CHUNK_SIZE", "1200"))
    CHUNK_OVERLAP: int = int(os.getenv("ZHIXUE_CHUNK_OVERLAP", "100"))
    ENABLE_IMAGE_PROCESSING: bool = True
    ENABLE_TABLE_PROCESSING: bool = True
    ENABLE_EQUATION_PROCESSING: bool = True

    # === 智学数据目录 ===
    ZHIXUE_DIR: str = "_zhixue"

    # === 多模型索引隔离 ===
    _rag_storage_dir_cache: str = ""

    # 缓存：避免每次都发 HTTP 请求
    _embedding_config_cache: dict = None
    _embedding_cache_valid: bool = False

    @staticmethod
    def _sanitize_model_name(model: str) -> str:
        """将模型名转为安全的目录名"""
        import re
        return re.sub(r'[^a-zA-Z0-9_-]', '_', model)

    @property
    def rag_storage_subdir(self) -> str:
        """根据当前 Embedding 模型 + Vault 路径计算子目录名，带缓存"""
        if self._rag_storage_dir_cache:
            return self._rag_storage_dir_cache
        
        # 基础：Embedding 模型名
        if self.EMBEDDING_MODEL:
            subdir = self._sanitize_model_name(self.EMBEDDING_MODEL)
        else:
            config = self.get_embedding_config()
            subdir = self._sanitize_model_name(config["model"])
        
        # 增强隔离：加入 Vault 路径 hash，避免不同 Vault 共享索引
        vault_path = self.vault_path
        if vault_path and vault_path.exists():
            import hashlib
            vault_hash = hashlib.md5(str(vault_path).encode()).hexdigest()[:8]
            subdir = f"{subdir}_{vault_hash}"
        
        self._rag_storage_dir_cache = subdir
        return subdir

    @property
    def vault_path(self) -> Path:
        """Vault 路径（自动检测）"""
        if self.VAULT_PATH and Path(self.VAULT_PATH).exists():
            return Path(self.VAULT_PATH)
        # 自动检测：向上查找含 .obsidian 的目录
        detected = self._detect_vault_path()
        if detected:
            return detected
        return Path(".")

    def _detect_vault_path(self) -> Path | None:
        """自动检测 Obsidian Vault 路径"""
        # 1. 从当前工作目录向上查找 .obsidian
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if (parent / ".obsidian").exists():
                print(f"[ZhiXue] 自动检测到 Vault 路径: {parent}")
                return parent
        # 2. Windows 常见路径
        home = Path.home()
        common_paths = [
            home / "Documents" / "Obsidian Vault",
            home / "Obsidian Vault",
        ]
        for p in common_paths:
            if p.exists() and (p / ".obsidian").exists():
                print(f"[ZhiXue] 自动检测到 Vault 路径: {p}")
                return p
        return None

    @property
    def working_dir(self) -> Path:
        if self.WORKING_DIR:
            return Path(self.WORKING_DIR)
        base = self.vault_path / self.ZHIXUE_DIR / "rag_storage"
        subdir = self.rag_storage_subdir
        return base / subdir

    @property
    def zhixue_dir(self) -> Path:
        return self.vault_path / self.ZHIXUE_DIR

    @property
    def conversations_dir(self) -> Path:
        return self.zhixue_dir / "conversations"

    @property
    def profile_path(self) -> Path:
        return self.zhixue_dir / "ai-profile.md"

    @property
    def habits_path(self) -> Path:
        return self.zhixue_dir / "habits.json"

    @property
    def active_llm_base_url(self) -> str:
        """优先使用用户显式配置的 LLM_BASE_URL，其次根据模型名自动推断，最后回退 Ollama"""
        if self.LLM_BASE_URL:
            return self.LLM_BASE_URL.rstrip("/")
        # 模型名含 "/" 说明是云端模型（如 deepseek-ai/DeepSeek-V3）
        # 此时 LLM_BASE_URL 为空是配置不完整，返回硅基流动默认值并打日志
        if "/" in self.LLM_MODEL:
            default_url = "https://api.siliconflow.cn/v1"
            logger.warning(
                f"[ZhiXue] LLM_BASE_URL 未配置，但模型 {self.LLM_MODEL} 是云端模型，"
                f"自动使用默认值 {default_url}。如需使用其他服务商，请在 .env 中设置 LLM_BASE_URL。"
            )
            return default_url
        return self.OLLAMA_BASE_URL.rstrip("/")

    @property
    def active_llm_api_key(self) -> str:
        """优先使用用户显式配置的 LLM_API_KEY，其次根据模型名自动推断，最后回退 Ollama"""
        if self.LLM_API_KEY:
            return self.LLM_API_KEY
        if "/" in self.LLM_MODEL:
            # 云端模型但没有配置 API Key，返回空字符串让 httpx 不挂 Authorization 头
            logger.warning(
                f"[ZhiXue] LLM_API_KEY 未配置，但模型 {self.LLM_MODEL} 是云端模型，"
                f"请在 .env 中设置 LLM_API_KEY。"
            )
            return ""
        return self.OLLAMA_API_KEY

    # === Embedding 最终配置（自动检测） ===
    @property
    def final_embedding_dim(self) -> int:
        """返回最终生效的 embedding 维度（优先从 get_embedding_config 获取）"""
        config = self.get_embedding_config()
        return config.get("dim", self.EMBEDDING_DIM or 768)

    @property
    def final_embedding_model(self) -> str:
        """返回最终生效的 embedding 模型名"""
        config = self.get_embedding_config()
        return config.get("model", self.EMBEDDING_MODEL or "nomic-embed-text")

    @property
    def final_embedding_api_key(self) -> str:
        """返回最终生效的 embedding API Key"""
        config = self.get_embedding_config()
        return config.get("api_key", self.EMBEDDING_API_KEY or self.OLLAMA_API_KEY)

    @property
    def final_embedding_base_url(self) -> str:
        """返回最终生效的 embedding Base URL"""
        config = self.get_embedding_config()
        return config.get("base_url", self.EMBEDDING_BASE_URL or self.OLLAMA_BASE_URL)

    # === Embedding 自动选择逻辑 ===

    def _check_ollama_running(self) -> bool:
        """检测 Ollama 是否运行"""
        try:
            import requests
            resp = requests.get(self.OLLAMA_BASE_URL.replace("/v1", "/api/tags"), timeout=2)
            return resp.status_code == 200
        except:
            return False

    def _check_embedding_available(self, model: str, base_url: str, api_key: str) -> bool:
        """检测指定 Embedding 模型是否可用"""
        try:
            import requests
            if "localhost" in base_url or "127.0.0.1" in base_url:
                url = base_url.replace("/v1", "/api/embeddings")
                resp = requests.post(url, json={"model": model, "prompt": "test"}, timeout=3)
            else:
                url = base_url.rstrip("/") + "/embeddings"
                resp = requests.post(url, json={"model": model, "input": ["test"]},
                                    headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
            return resp.status_code in [200, 201]
        except:
            return False

    def get_embedding_config(self, force_refresh: bool = False) -> dict:
        """获取 Embedding 配置（智能选择）"""
        if not force_refresh and self._embedding_cache_valid and self._embedding_config_cache:
            return self._embedding_config_cache

        # 0. 如果已有索引，优先复用索引的模型配置（避免维度不匹配）
        existing_model_info = self._get_existing_index_model_info()
        if existing_model_info:
            model = existing_model_info.get("embedding_model", "")
            dim = existing_model_info.get("embedding_dim", 0)
            if model and dim:
                print(f"[ZhiXue] 检测到已有索引: model={model}, dim={dim}，直接复用")
                result = {"model": model, "dim": dim, "base_url": self.OLLAMA_BASE_URL, "api_key": self.OLLAMA_API_KEY}
                self._embedding_config_cache = result
                self._embedding_cache_valid = True
                return result

        # 1. 如果指定了云端来源，优先用云端配置
        if self.EMBEDDING_SOURCE == "cloud":
            if self.EMBEDDING_BASE_URL and self.EMBEDDING_API_KEY:
                model = self.EMBEDDING_MODEL or "BAAI/bge-m3"
                url = self.EMBEDDING_BASE_URL
                key = self.EMBEDDING_API_KEY
                dim = self.EMBEDDING_DIM
                if dim == 0:
                    dim = 1024 if "bge-m3" in model else (1536 if "text-embedding-3" in model else 768)
                if self._check_embedding_available(model, url, key):
                    result = {"model": model, "dim": dim, "base_url": url, "api_key": key}
                    self._embedding_config_cache = result
                    self._embedding_cache_valid = True
                    return result
                else:
                    print(f"[ZhiXue] 云端 Embedding 模型 {model} 不可用，自动切换...")

        # 1. 用户显式配置了模型
        if self.EMBEDDING_MODEL:
            model = self.EMBEDDING_MODEL
            if self.EMBEDDING_BASE_URL:
                url = self.EMBEDDING_BASE_URL
            elif "/" in model:
                url = "https://api.siliconflow.cn/v1" if "BAAI/" in model else ("https://api.openai.com/v1" if "text-embedding" in model else self.active_llm_base_url)
            else:
                url = self.OLLAMA_BASE_URL
            key = self.EMBEDDING_API_KEY or (self.active_llm_api_key if "/" in model else self.OLLAMA_API_KEY)
            dim = self.EMBEDDING_DIM
            if dim == 0:
                dim = 1024 if "bge-m3" in model else (1536 if "text-embedding-3" in model else 768)
            if self._check_embedding_available(model, url, key):
                result = {"model": model, "dim": dim, "base_url": url, "api_key": key}
                self._embedding_config_cache = result
                self._embedding_cache_valid = True
                return result
            else:
                print(f"[ZhiXue] 配置的 Embedding 模型 {model} 不可用，自动切换...")

        # 2. 自动选择：优先本地 Ollama
        if self._check_ollama_running():
            if self._check_embedding_available("nomic-embed-text", self.OLLAMA_BASE_URL, self.OLLAMA_API_KEY):
                result = {"model": "nomic-embed-text", "dim": 768, "base_url": self.OLLAMA_BASE_URL, "api_key": self.OLLAMA_API_KEY}
                self._embedding_config_cache = result
                self._embedding_cache_valid = True
                return result

        # 3. 云端（根据 LLM 配置）
        if self.LLM_API_KEY:
            if "siliconflow" in (self.LLM_BASE_URL or ""):
                url = "https://api.siliconflow.cn/v1"
                if self._check_embedding_available("BAAI/bge-m3", url, self.LLM_API_KEY):
                    result = {"model": "BAAI/bge-m3", "dim": 1024, "base_url": url, "api_key": self.LLM_API_KEY}
                    self._embedding_config_cache = result
                    self._embedding_cache_valid = True
                    return result

        # 4. Ollama 兜底
        result = {"model": "nomic-embed-text", "dim": 768, "base_url": self.OLLAMA_BASE_URL, "api_key": self.OLLAMA_API_KEY}
        self._embedding_config_cache = result
        self._embedding_cache_valid = True
        return result

    def invalidate_embedding_cache(self):
        self._embedding_cache_valid = False
        self._embedding_config_cache = None
        self._rag_storage_dir_cache = ""

    def _get_existing_index_model_info(self) -> dict | None:
        """检查 working_dir 下是否有已有索引，返回其 model_info"""
        try:
            info_file = self.working_dir / "model_info.json"
            if info_file.exists():
                import json
                with open(info_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    # === 配置校验 ===
    def validate(self) -> list[str]:
        """校验配置，返回错误列表（空列表表示全部通过）"""
        errors = []

        # 1. 校验 Vault 路径
        if not self.vault_path or not self.vault_path.exists():
            errors.append(f"Vault 路径不存在: {self.VAULT_PATH}（也未自动检测到）")

        # 2. 校验端口号
        if not (1 <= self.PORT <= 65535):
            errors.append(f"端口号无效: {self.PORT}（必须是 1-65535）")

        # 3. 静态校验 Embedding 配置（不发起网络请求）
        if self.EMBEDDING_SOURCE == "cloud":
            if not self.EMBEDDING_BASE_URL:
                errors.append("Embedding 来源为云端，但未配置 EMBEDDING_BASE_URL")
            if not self.EMBEDDING_API_KEY:
                errors.append("Embedding 来源为云端，但未配置 EMBEDDING_API_KEY")
        elif not self.EMBEDDING_MODEL:
            # 本地模式：检查是否配置了模型名
            errors.append("Embedding 模型未配置（请在 .env 中设置 ZHIXUE_EMBEDDING_MODEL）")

        # 4. 校验 LLM 配置（仅静态检查）
        if "/" in self.LLM_MODEL:
            # 云端模型
            if not self.LLM_BASE_URL and not self.OLLAMA_BASE_URL:
                errors.append(f"LLM 模型 {self.LLM_MODEL} 是云端模型，但未配置 LLM_BASE_URL")
            if not self.LLM_API_KEY and not self.OLLAMA_API_KEY:
                errors.append(f"LLM 模型 {self.LLM_MODEL} 是云端模型，但未配置 API Key")
        elif not self.LLM_MODEL:
            errors.append("LLM 模型未配置")

        # 5. 校验工作目录（尝试创建，检查权限）
        try:
            self.working_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"工作目录无法创建: {self.working_dir} ({e})")

        return errors


settings = Settings()
