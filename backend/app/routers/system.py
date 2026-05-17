"""
智学 (ZhiXue) - 系统状态 API
"""
import logging
from pathlib import Path
from typing import Optional

import httpx
from dotenv import set_key
from fastapi import APIRouter
from pydantic import BaseModel

from ..rag_engine import rag_engine
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["system"])

# .env 文件路径（system.py 在 app/routers/ 下，需要上溯三层到 backend/ 根目录）
_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


@router.get("/status")
async def system_status():
    """系统状态检查"""
    rag_status = await rag_engine.get_status()
    return {
        "status": "ok",
        "version": "0.1.0",
        "rag": rag_status,
        "vault_path": str(settings.vault_path),
    }


@router.get("/config")
async def system_config():
    """获取当前配置"""
    return {
        "host": settings.HOST,
        "port": settings.PORT,
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "ollama_base_url": settings.OLLAMA_BASE_URL,
        "llm_base_url": settings.LLM_BASE_URL,
        "llm_api_key": "***" + settings.LLM_API_KEY[-4:] if len(settings.LLM_API_KEY) > 4 else "***" if settings.LLM_API_KEY else "",
        "active_llm_base_url": settings.active_llm_base_url,
        "active_llm_api_key": "***" + settings.active_llm_api_key[-4:] if len(settings.active_llm_api_key) > 4 else "***" if settings.active_llm_api_key else "",
        "vault_path": str(settings.vault_path),
        "working_dir": str(settings.working_dir),
        "parser": settings.PARSER,
    }


@router.get("/check-models")
async def check_ollama_models():
    """检查 Ollama 中是否已安装所需模型

    返回 LLM 和 Embedding 模型的安装状态，
    以及如何安装未找到的模型的说明。
    """
    result = {
        "ollama_running": False,
        "llm_model": {
            "name": settings.LLM_MODEL,
            "installed": False,
        },
        "embedding_model": {
            "name": settings.EMBEDDING_MODEL,
            "installed": False,
        },
        "instructions": [],
    }

    # 检查 Ollama 是否运行
    ollama_host = settings.OLLAMA_BASE_URL.replace("/v1", "")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ollama_host}/api/tags")
            if resp.status_code != 200:
                result["instructions"].append(
                    "Ollama 未运行，请先启动 Ollama"
                )
                return result

            result["ollama_running"] = True
            models_data = resp.json()
            installed_models = [
                m.get("name", "")
                for m in models_data.get("models", [])
            ]
            # 同时构建不带 tag 的列表，用于模糊匹配
            installed_models_base = [n.split(":")[0] for n in installed_models]

            # 检查 LLM 模型（精确匹配或基础名匹配）
            llm_installed = (
                settings.LLM_MODEL in installed_models
                or settings.LLM_MODEL.split(":")[0] in installed_models_base
            )
            result["llm_model"]["installed"] = llm_installed
            if not llm_installed:
                result["instructions"].append(
                    f"LLM 模型 {settings.LLM_MODEL} 未安装，"
                    f"请运行: ollama pull {settings.LLM_MODEL}"
                )

            # 检查 Embedding 模型（精确匹配或基础名匹配）
            emb_installed = (
                settings.EMBEDDING_MODEL in installed_models
                or settings.EMBEDDING_MODEL.split(":")[0] in installed_models_base
            )
            result["embedding_model"]["installed"] = emb_installed
            if not emb_installed:
                result["instructions"].append(
                    f"Embedding 模型 {settings.EMBEDDING_MODEL} 未安装，"
                    f"请运行: ollama pull {settings.EMBEDDING_MODEL}"
                )

            if llm_installed and emb_installed:
                result["instructions"].append("所有模型已就绪！")

    except httpx.ConnectError:
        result["instructions"].append(
            "无法连接到 Ollama，请确认 Ollama 是否正在运行"
        )
    except Exception as e:
        logger.error(f"检查 Ollama 模型失败: {e}")
        result["instructions"].append(f"检查模型时出错: {str(e)}")

    return result


class SwitchModelRequest(BaseModel):
    """切换模型请求"""
    model_type: str  # "llm" | "embedding"
    model_name: str
    embedding_dim: Optional[int] = None  # embedding 维度（切换 embedding 时建议提供）


class UpdateConfigRequest(BaseModel):
    """更新配置请求"""
    ollama_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None
    llm_base_url: Optional[str] = None   # LLM 独立 API 地址（如硅基流动）
    llm_api_key: Optional[str] = None    # LLM 独立 API Key
    llm_model: Optional[str] = None      # LLM 模型名（同步前端选择的模型）
    embedding_base_url: Optional[str] = None   # Embedding 云端 API 地址
    embedding_api_key: Optional[str] = None  # Embedding 云端 API Key
    embedding_source: Optional[str] = None    # "ollama" | "cloud"


@router.get("/list-models")
async def list_ollama_models():
    """列出 Ollama 中所有已安装的模型

    返回模型名称、大小和修改时间，供前端选择切换。
    """
    ollama_host = settings.OLLAMA_BASE_URL.replace("/v1", "")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ollama_host}/api/tags")
            if resp.status_code != 200:
                return {"ollama_running": False, "models": []}

            models_data = resp.json()
            models = []
            for m in models_data.get("models", []):
                models.append({
                    "name": m.get("name", ""),
                    "size_gb": round(m.get("size", 0) / 1e9, 2),
                    "modified": m.get("modified_at", ""),
                })

            return {
                "ollama_running": True,
                "models": models,
                "current_llm": settings.LLM_MODEL,
                "current_embedding": settings.EMBEDDING_MODEL,
            }
    except httpx.ConnectError:
        return {"ollama_running": False, "models": [], "current_llm": settings.LLM_MODEL, "current_embedding": settings.EMBEDDING_MODEL}
    except Exception as e:
        logger.error(f"列出 Ollama 模型失败: {e}")
        return {"ollama_running": False, "models": [], "error": str(e), "current_llm": settings.LLM_MODEL, "current_embedding": settings.EMBEDDING_MODEL}


@router.put("/switch-model")
async def switch_model(req: SwitchModelRequest):
    """运行时切换 LLM 或 Embedding 模型

    直接修改 settings 中的模型名，闭包会在下次调用时自动读取新值，
    无需重新初始化 RAG 引擎。
    """
    if req.model_type == "llm":
        old_model = settings.LLM_MODEL
        settings.LLM_MODEL = req.model_name

        # 根据新模型名自动设置/清除 LLM_BASE_URL 和 LLM_API_KEY
        # 模型名含 "/" → 云端模型（如 deepseek-ai/DeepSeek-V3）
        # 模型名不含 "/" → 本地 Ollama 模型（如 deepseek-r1:7b）
        if "/" in req.model_name:
            # 切换到云端模型：若 LLM_BASE_URL 未设置，则自动填入硅基流动默认值
            if not settings.LLM_BASE_URL:
                settings.LLM_BASE_URL = "https://api.siliconflow.cn/v1"
                set_key(_ENV_FILE, "LLM_BASE_URL", settings.LLM_BASE_URL)
            # LLM_API_KEY 不由切换逻辑自动设置，保留用户已配置的值（在 .env 中）
        else:
            # 切换到 Ollama 模型：清除云端配置，让 active_llm_base_url 回退到 OLLAMA_BASE_URL
            settings.LLM_BASE_URL = ""
            settings.LLM_API_KEY = ""
            set_key(_ENV_FILE, "LLM_BASE_URL", "")
            set_key(_ENV_FILE, "LLM_API_KEY", "")

        set_key(_ENV_FILE, "ZHIXUE_LLM_MODEL", req.model_name)
        logger.info(f"LLM 模型已切换为: {req.model_name}")

        # 如果是从 API 模型切换到 Ollama 模型，或反过来，
        # 需要清除 RAG 引擎的初始化状态，因为 LLM 配置变了
        old_is_api = "/" in old_model
        new_is_api = "/" in req.model_name
        if old_is_api != new_is_api or rag_engine._init_error:
            logger.info("LLM 配置类型变化，重置 RAG 引擎初始化状态")
            rag_engine._initialized = False
            rag_engine._init_error = None
            rag_engine.rag = None

        return {
            "status": "ok",
            "model_type": "llm",
            "active_model": settings.LLM_MODEL,
            "message": f"LLM 模型已切换为 {req.model_name}，下次查询生效",
        }
    elif req.model_type == "embedding":
        if req.embedding_dim is not None:
            settings.EMBEDDING_DIM = req.embedding_dim
            set_key(_ENV_FILE, "ZHIXUE_EMBEDDING_DIM", str(req.embedding_dim))
        settings.EMBEDDING_MODEL = req.model_name
        set_key(_ENV_FILE, "ZHIXUE_EMBEDDING_MODEL", req.model_name)

        # 清除 Embedding 配置缓存，强制重新检测
        settings.invalidate_embedding_cache()

        # 重置 RAG 引擎，下次查询会重新初始化（使用新模型和新 working_dir）
        rag_engine._initialized = False
        rag_engine._init_error = None
        rag_engine.rag = None

        logger.info(f"Embedding 模型已切换为: {req.model_name}")
        return {
            "status": "ok",
            "model_type": "embedding",
            "active_model": settings.EMBEDDING_MODEL,
            "working_dir": str(settings.working_dir),
            "message": f"Embedding 模型已切换为 {req.model_name}，下次查询将使用新索引目录",
        }
    else:
        return {
            "status": "error",
            "message": f"不支持的模型类型: {req.model_type}，请使用 'llm' 或 'embedding'",
        }


@router.put("/update-config")
async def update_config(req: UpdateConfigRequest):
    """更新运行时配置（API Key、Ollama 地址等）

    修改后立即生效，下次查询时使用新配置。
    """
    updated = []
    if req.ollama_api_key is not None:
        settings.OLLAMA_API_KEY = req.ollama_api_key
        updated.append("Ollama API Key")

    if req.ollama_base_url is not None:
        url = req.ollama_base_url.rstrip("/")
        if not url.endswith("/v1"):
            url = url + "/v1"
        settings.OLLAMA_BASE_URL = url
        updated.append("Ollama 地址")

    if req.llm_model is not None:
        old_model = settings.LLM_MODEL
        settings.LLM_MODEL = req.llm_model
        set_key(_ENV_FILE, "ZHIXUE_LLM_MODEL", req.llm_model)
        updated.append("LLM 模型")

        # 如果模型类型变化（本地 ↔ 云端），重置 RAG 引擎
        old_is_api = "/" in old_model
        new_is_api = "/" in req.llm_model
        if old_is_api != new_is_api or rag_engine._init_error:
            logger.info("LLM 配置类型变化，重置 RAG 引擎初始化状态")
            rag_engine._initialized = False
            rag_engine._init_error = None
            rag_engine.rag = None

    if req.llm_api_key is not None:
        settings.LLM_API_KEY = req.llm_api_key
        set_key(_ENV_FILE, "LLM_API_KEY", req.llm_api_key)
        updated.append("LLM API Key")

    if req.llm_base_url is not None:
        url = req.llm_base_url.rstrip("/")
        if not url.endswith("/v1"):
            url = url + "/v1"
        settings.LLM_BASE_URL = url
        set_key(_ENV_FILE, "LLM_BASE_URL", url)
        updated.append("LLM API 地址")

    if req.embedding_api_key is not None:
        settings.EMBEDDING_API_KEY = req.embedding_api_key
        set_key(_ENV_FILE, "ZHIXUE_EMBEDDING_API_KEY", req.embedding_api_key)
        updated.append("Embedding API Key")
        settings.invalidate_embedding_cache()

    if req.embedding_base_url is not None:
        url = req.embedding_base_url.rstrip("/")
        if not url.endswith("/v1"):
            url = url + "/v1"
        settings.EMBEDDING_BASE_URL = url
        set_key(_ENV_FILE, "ZHIXUE_EMBEDDING_BASE_URL", url)
        updated.append("Embedding API 地址")
        settings.invalidate_embedding_cache()

    if req.embedding_source is not None:
        settings.EMBEDDING_SOURCE = req.embedding_source
        set_key(_ENV_FILE, "ZHIXUE_EMBEDDING_SOURCE", req.embedding_source)
        updated.append("Embedding 来源")
        settings.invalidate_embedding_cache()

    logger.info(f"配置已更新并持久化: {', '.join(updated)}")
    return {
        "status": "ok",
        "updated": updated,
        "config": {
            "ollama_api_key": "***" + settings.OLLAMA_API_KEY[-4:] if len(settings.OLLAMA_API_KEY) > 4 else "***",
            "ollama_base_url": settings.OLLAMA_BASE_URL,
            "llm_api_key": "***" + settings.active_llm_api_key[-4:] if len(settings.active_llm_api_key) > 4 else "***",
            "llm_base_url": settings.active_llm_base_url,
            "llm_model": settings.LLM_MODEL,
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_source": getattr(settings, "EMBEDDING_SOURCE", "ollama"),
            "embedding_base_url": getattr(settings, "EMBEDDING_BASE_URL", ""),
        },
    }
