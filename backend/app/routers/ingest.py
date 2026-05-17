"""
智学 (ZhiXue) - 文档摄取 API
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..rag_engine import rag_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestFileRequest(BaseModel):
    file_path: str


class IngestVaultRequest(BaseModel):
    force: bool = False


@router.post("/file")
async def ingest_file(req: IngestFileRequest):
    """摄取单个文件"""
    result = await rag_engine.ingest_file(req.file_path)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "摄取失败"))
    return result


@router.post("/vault")
async def ingest_vault(req: IngestVaultRequest):
    """全量摄取 Vault"""
    result = await rag_engine.ingest_vault(force=req.force)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "摄取失败"))
    return result


@router.get("/status")
async def ingest_status():
    """获取摄取状态"""
    return await rag_engine.get_status()
