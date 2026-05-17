"""
智学 (ZhiXue) - 对话 API
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..rag_engine import rag_engine
from ..ai_profile import ai_profile
from ..habit_tracker import habit_tracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


class MessageItem(BaseModel):
    """对话历史中的单条消息"""
    role: str  # "user" | "assistant"
    content: str


class QueryRequest(BaseModel):
    question: str
    mode: str = "hybrid"  # hybrid / local / global / naive
    conversation_id: Optional[str] = None
    current_note: Optional[str] = None  # 当前打开的笔记路径
    history: Optional[list[MessageItem]] = None  # 对话历史（最近几轮）


class QueryResponse(BaseModel):
    status: str = "success"  # "success" | "error"
    answer: str = ""
    sources: list = []
    related_notes: list = []
    mode: str = "hybrid"
    conversation_id: Optional[str] = None
    error_type: Optional[str] = None  # init_error / timeout / ollama_connection / model_missing / resource_error / query_error
    message: Optional[str] = None  # 错误时的可读信息


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """智能问答（核心 API）"""
    # 构建增强查询（融合对话历史）
    enhanced_question = req.question
    if req.history and len(req.history) > 0:
        recent = req.history[-8:]
        context_parts = []
        for msg in recent:
            role_label = "用户" if msg.role == "user" else "AI"
            context_parts.append(f"{role_label}：{msg.content[:200]}")
        context_str = "\n".join(context_parts)
        enhanced_question = (
            f"【对话上下文】\n{context_str}\n\n"
            f"【当前问题】{req.question}"
        )

    # 执行 RAG 查询
    result = await rag_engine.query(enhanced_question, mode=req.mode)

    if result["status"] == "error":
        # 返回结构化错误而非 HTTP 500，前端可以据此展示友好提示
        return QueryResponse(
            status="error",
            answer=result.get("message", "查询失败"),
            error_type=result.get("error_type", "query_error"),
            message=result.get("message", "查询失败"),
            mode=req.mode,
        )

    # 记录查询习惯
    notes_accessed = result.get("sources", [])
    try:
        await habit_tracker.record_query(
            query=req.question,
            notes_accessed=notes_accessed if isinstance(notes_accessed, list) else [],
            topic=_extract_topic(req.question),
        )
    except Exception as e:
        logger.warning(f"记录查询习惯失败: {e}")

    try:
        habits_summary = await habit_tracker.build_habits_summary()
        await ai_profile.update_habits_section(habits_summary)
    except Exception as e:
        logger.warning(f"更新 AI 印象失败: {e}")

    # 获取推荐笔记
    recommendations = {}
    try:
        recommendations = await habit_tracker.get_recommendations(req.current_note)
    except Exception as e:
        logger.warning(f"获取推荐笔记失败: {e}")

    return QueryResponse(
        answer=result["answer"],
        sources=result.get("sources", []),
        related_notes=recommendations.get("frequent_notes", []) if recommendations else [],
        mode=req.mode,
        conversation_id=req.conversation_id,
    )


def _extract_topic(question: str) -> str:
    """简单提取查询主题（取前几个字作为粗略主题）"""
    return question[:20] if len(question) > 20 else question
