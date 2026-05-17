"""
智学 (ZhiXue) - FastAPI 主入口
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .rag_engine import rag_engine
from .ai_profile import ai_profile
from .habit_tracker import habit_tracker
from .routers import chat, ingest, profile, habits, system

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化，关闭时清理"""
    logger.info("=" * 50)
    logger.info("智学 (ZhiXue) 后端启动中...")
    
    # 配置校验
    errors = settings.validate()
    if errors:
        logger.error("配置校验失败：")
        for err in errors:
            logger.error(f"  - {err}")
    else:
        logger.info("配置校验通过 ✓")
    
    logger.info(f"Vault 路径: {settings.vault_path}")
    logger.info(f"LLM 模型: {settings.LLM_MODEL}")
    logger.info(f"Embedding: {settings.EMBEDDING_MODEL}")
    logger.info("=" * 50)

    # 轻量模块同步初始化
    try:
        await ai_profile.initialize()
        logger.info("AI 印象模块已初始化")
    except Exception as e:
        logger.warning(f"AI 印象初始化失败: {e}")

    try:
        await habit_tracker.initialize()
        logger.info("习惯追踪模块已初始化")
    except Exception as e:
        logger.warning(f"习惯追踪初始化失败: {e}")

    # RAG 引擎在后台异步初始化（不阻塞服务器就绪）
    logger.info("RAG 引擎将在后台初始化...")
    asyncio.create_task(rag_engine.initialize_background())

    # 服务器立即就绪，不等 RAG
    logger.info("智学后端已就绪！（RAG 引擎后台加载中）")

    yield

    # 关闭时清理
    logger.info("智学后端关闭中...")


# 创建 FastAPI 应用
app = FastAPI(
    title="智学 (ZhiXue)",
    description="RAG-Anything 驱动的 AI 知识助手后端",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 中间件（允许 Obsidian 插件访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(habits.router, prefix="/api")
app.include_router(system.router, prefix="/api")


@app.get("/")
async def root():
    return {"name": "智学 (ZhiXue)", "version": "0.1.0", "status": "running"}
