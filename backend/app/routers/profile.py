"""
智学 (ZhiXue) - AI 印象 API
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..ai_profile import ai_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileUpdateRequest(BaseModel):
    content: str  # 完整的 Markdown 内容


@router.get("")
async def get_profile():
    """获取 AI 印象"""
    return await ai_profile.load_profile()


@router.put("")
async def update_profile(req: ProfileUpdateRequest):
    """更新 AI 印象"""
    result = await ai_profile.save_profile(req.content)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "更新失败"))
    return result
