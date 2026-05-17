"""
智学 (ZhiXue) - 使用习惯 API
"""
import logging
from fastapi import APIRouter
from typing import Optional

from ..habit_tracker import habit_tracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/habits", tags=["habits"])


@router.get("")
async def get_habits():
    """获取使用习惯数据"""
    return await habit_tracker.get_habits_data()


@router.get("/recommendations")
async def get_recommendations(current_note: str = None):
    """获取推荐笔记和主题"""
    return await habit_tracker.get_recommendations(current_note)


@router.get("/topics")
async def get_frequent_topics(top_k: int = 10):
    """获取高频主题"""
    return await habit_tracker.get_frequent_topics(top_k)


@router.get("/notes")
async def get_frequent_notes(top_k: int = 10):
    """获取高频笔记"""
    return await habit_tracker.get_frequent_notes(top_k)
