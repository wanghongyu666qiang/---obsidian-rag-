"""
智学 (ZhiXue) - 使用习惯追踪
记录用户查询习惯、常问主题、高频笔记，反馈到 AI 印象
"""
import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)

DEFAULT_HABITS = {
    "total_queries": 0,
    "topics": {},
    "frequent_notes": [],
    "query_history": [],
}


class HabitTracker:
    """追踪用户使用习惯"""

    def __init__(self):
        self._data: dict = {}
        self._max_history = 100  # 最多保留 100 条查询记录

    async def initialize(self):
        """初始化，读取或创建习惯文件"""
        habits_path = settings.habits_path
        habits_path.parent.mkdir(parents=True, exist_ok=True)

        if habits_path.exists():
            try:
                self._data = json.loads(habits_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"读取习惯文件失败，使用默认值: {e}")
                self._data = DEFAULT_HABITS.copy()
        else:
            self._data = DEFAULT_HABITS.copy()
            self._save()

    def _save(self):
        """保存习惯数据"""
        habits_path = settings.habits_path
        habits_path.parent.mkdir(parents=True, exist_ok=True)
        habits_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def record_query(
        self,
        query: str,
        notes_accessed: list[str] = None,
        topic: str = None,
    ):
        """记录一次查询"""
        self._data["total_queries"] += 1

        now = datetime.now().isoformat()

        # 记录查询历史
        record = {
            "time": now,
            "query": query[:200],  # 截断长查询
        }
        if notes_accessed:
            record["notes_accessed"] = notes_accessed[:10]  # 最多 10 条

        self._data["query_history"].append(record)

        # 限制历史记录数量
        if len(self._data["query_history"]) > self._max_history:
            self._data["query_history"] = self._data["query_history"][-self._max_history:]

        # 更新主题计数
        if topic:
            topics = self._data.setdefault("topics", {})
            if topic not in topics:
                topics[topic] = {"count": 0, "last_queried": ""}
            topics[topic]["count"] += 1
            topics[topic]["last_queried"] = now

        # 更新高频笔记
        if notes_accessed:
            note_counter = Counter(self._data.get("frequent_notes", []))
            for note in notes_accessed:
                note_counter[note] += 1
            # 保留 Top 20
            self._data["frequent_notes"] = [
                note for note, _ in note_counter.most_common(20)
            ]

        self._save()

    async def get_frequent_topics(self, top_k: int = 10) -> list[dict]:
        """获取高频主题"""
        topics = self._data.get("topics", {})
        sorted_topics = sorted(
            topics.items(), key=lambda x: x[1].get("count", 0), reverse=True
        )
        return [
            {"topic": t, "count": d.get("count", 0), "last_queried": d.get("last_queried", "")}
            for t, d in sorted_topics[:top_k]
        ]

    async def get_frequent_notes(self, top_k: int = 10) -> list[str]:
        """获取高频访问的笔记"""
        return self._data.get("frequent_notes", [])[:top_k]

    async def get_recommendations(self, current_note: str = None) -> dict:
        """获取推荐笔记和主题"""
        frequent_topics = await self.get_frequent_topics(5)
        frequent_notes = await self.get_frequent_notes(5)

        return {
            "frequent_topics": frequent_topics,
            "frequent_notes": frequent_notes,
            "current_note": current_note,
        }

    async def get_habits_data(self) -> dict:
        """获取完整习惯数据"""
        return self._data.copy()

    async def build_habits_summary(self) -> str:
        """构建习惯摘要文本，用于更新 AI 印象"""
        topics = await self.get_frequent_topics(5)
        notes = await self.get_frequent_notes(5)

        lines = []
        if topics:
            topic_str = "、".join([t["topic"] for t in topics])
            lines.append(f"- 常问主题：{topic_str}")
        else:
            lines.append("- 常问主题：暂无")

        if notes:
            note_str = "、".join([Path(n).stem for n in notes])
            lines.append(f"- 高频笔记：{note_str}")
        else:
            lines.append("- 高频笔记：暂无")

        lines.append(f"- 总查询次数：{self._data.get('total_queries', 0)}")

        return "\n".join(lines)


# 全局单例
habit_tracker = HabitTracker()
