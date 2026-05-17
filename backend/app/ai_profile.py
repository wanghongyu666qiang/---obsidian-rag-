"""
智学 (ZhiXue) - AI 印象管理
AI 的人格、记忆和对用户的理解，存储在 Vault 中的 Markdown 文件里
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = """---
type: zhixue-ai-profile
created: {created}
updated: {updated}
---

## AI 人格
你是一个温暖、有耐心的学习伙伴。你的名字叫"小智"。
你会根据用户的笔记内容给出精准、有深度的回答，并主动关联相关知识。

## 关于用户
- 学习风格：待了解
- 擅长领域：待了解
- 偏好语言：中文
- 常用笔记工具：Obsidian

## 使用习惯摘要
- 常问主题：暂无
- 高频笔记：暂无
- 交互风格：待了解

## 特别指令
- 回答时尽量引用用户 Vault 中的已有笔记
- 如果不确定，诚实说明，不要编造
- 用中文回答，除非用户用其他语言提问
"""


class AIProfile:
    """AI 人格和记忆管理"""

    def __init__(self):
        self._profile_content: str = ""
        self._personality: str = ""
        self._about_user: str = ""
        self._special_instructions: str = ""

    async def initialize(self):
        """初始化 AI 印象，读取或创建默认文件"""
        profile_path = settings.profile_path
        profile_path.parent.mkdir(parents=True, exist_ok=True)

        if profile_path.exists():
            self._profile_content = profile_path.read_text(encoding="utf-8")
        else:
            now = datetime.now().strftime("%Y-%m-%d")
            self._profile_content = DEFAULT_PROFILE.format(created=now, updated=now)
            profile_path.write_text(self._profile_content, encoding="utf-8")
            logger.info("已创建默认 AI 印象文件")

        self._parse_profile()

    def _parse_profile(self):
        """解析 profile 文件各部分"""
        content = self._profile_content

        # 提取各 section 内容
        sections = {}
        current_section = None
        current_lines = []

        for line in content.split("\n"):
            if line.startswith("## "):
                if current_section:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = line[3:].strip()
                current_lines = []
            elif current_section:
                current_lines.append(line)

        if current_section:
            sections[current_section] = "\n".join(current_lines).strip()

        self._personality = sections.get("AI 人格", "")
        self._about_user = sections.get("关于用户", "")
        self._special_instructions = sections.get("特别指令", "")
        self._habits_summary = sections.get("使用习惯摘要", "")

    async def build_system_prompt(self) -> str:
        """构建完整的 system prompt，融合 AI 人格 + 用户画像 + 习惯"""
        parts = []

        if self._personality:
            parts.append(f"【你的身份和性格】\n{self._personality}")

        if self._about_user:
            parts.append(f"【关于你的用户】\n{self._about_user}")

        if self._habits_summary:
            parts.append(f"【用户的使用习惯】\n{self._habits_summary}")

        if self._special_instructions:
            parts.append(f"【特别指令】\n{self._special_instructions}")

        if parts:
            return "\n\n".join(parts)

        return "你是智学 AI 助手，一个温暖、有耐心的学习伙伴。"

    async def load_profile(self) -> dict:
        """读取 AI 印象"""
        return {
            "content": self._profile_content,
            "personality": self._personality,
            "about_user": self._about_user,
            "special_instructions": self._special_instructions,
            "path": str(settings.profile_path),
        }

    async def save_profile(self, content: str) -> dict:
        """保存 AI 印象"""
        # 更新 frontmatter 中的 updated 时间
        now = datetime.now().strftime("%Y-%m-%d")
        lines = content.split("\n")
        new_lines = []
        in_frontmatter = False

        for line in lines:
            if line.strip() == "---":
                in_frontmatter = not in_frontmatter
                new_lines.append(line)
            elif in_frontmatter and line.startswith("updated:"):
                new_lines.append(f"updated: {now}")
            else:
                new_lines.append(line)

        updated_content = "\n".join(new_lines)

        profile_path = settings.profile_path
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(updated_content, encoding="utf-8")

        self._profile_content = updated_content
        self._parse_profile()

        logger.info("AI 印象已更新")
        return {"status": "success", "message": "AI 印象已保存"}

    async def update_habits_section(self, habits_summary: str):
        """更新使用习惯摘要部分"""
        lines = self._profile_content.split("\n")
        new_lines = []
        in_habits = False

        for i, line in enumerate(lines):
            if line.startswith("## 使用习惯摘要"):
                in_habits = True
                new_lines.append(line)
                continue
            elif line.startswith("## ") and in_habits:
                in_habits = False

            if in_habits:
                # 跳过旧内容，后面添加新内容
                continue
            else:
                new_lines.append(line)

        # 在使用习惯摘要 section 后插入新内容
        result = []
        for line in new_lines:
            result.append(line)
            if line.startswith("## 使用习惯摘要"):
                result.append(habits_summary)

        self._profile_content = "\n".join(result)
        self._parse_profile()

        # 保存到文件
        profile_path = settings.profile_path
        profile_path.write_text(self._profile_content, encoding="utf-8")


# 全局单例
ai_profile = AIProfile()
