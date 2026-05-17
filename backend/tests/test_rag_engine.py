"""
测试 RAG 引擎的独立功能（不加载重型依赖）
"""
import pytest
import sys
from unittest.mock import patch, MagicMock

# 模拟 heavy imports
mock_modules = {
    'lightrag': MagicMock(),
    'lightrag.llm.openai': MagicMock(),
    'lightrag.utils': MagicMock(),
    'raganything': MagicMock(),
}

with patch.dict(sys.modules, mock_modules):
    from app.rag_engine import RAGEngine


class TestFilterThinkingTags:
    """测试思考标签过滤"""

    def test_none_input(self):
        """测试 None 输入"""
        result = RAGEngine._filter_thinking_tags(None)
        assert result == ""

    def test_empty_string(self):
        """测试空字符串"""
        result = RAGEngine._filter_thinking_tags("")
        assert result == ""

    def test_no_thinking_tags(self):
        """测试无思考标签的文本"""
        text = "这是正常的回答内容"
        result = RAGEngine._filter_thinking_tags(text)
        assert result == text

    def test_with_thinking_tags(self):
        """测试包含思考标签的文本"""
        text = "💭 我在思考...\n\n这是真正的回答"
        result = RAGEngine._filter_thinking_tags(text)
        assert "💭" not in result
        assert "这是真正的回答" in result

    def test_multiple_newlines(self):
        """测试多个换行符被归一化"""
        text = "第一行\n\n\n\n第二行"
        result = RAGEngine._filter_thinking_tags(text)
        assert "\n\n\n" not in result


class TestFindMinerUContentList:
    """测试 MinerU 缓存文件查找"""

    def test_find_existing_file(self, tmp_path):
        """测试找到存在的文件"""
        # 创建模拟的 MinerU 输出结构
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_text("mock pdf")

        output_dir = tmp_path / "output"
        sub_dir = output_dir / "test_abc123"
        sub_dir.mkdir(parents=True)
        
        content_list_file = sub_dir / "test_content_list.json"
        content_list_file.write_text('[{"type": "text"}]')

        result = RAGEngine._find_mineru_content_list(str(pdf_path), output_dir)
        assert result is not None
        assert "test_content_list.json" in str(result)

    def test_no_matching_dir(self, tmp_path):
        """测试没有匹配的目录"""
        pdf_path = tmp_path / "test.pdf"
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = RAGEngine._find_mineru_content_list(str(pdf_path), output_dir)
        assert result is None

    def test_wrong_stem(self, tmp_path):
        """测试目录名不匹配"""
        pdf_path = tmp_path / "test.pdf"
        output_dir = tmp_path / "output"
        
        # 创建不匹配的目录
        wrong_dir = output_dir / "other_abc123"
        wrong_dir.mkdir(parents=True)
        
        result = RAGEngine._find_mineru_content_list(str(pdf_path), output_dir)
        assert result is None


class TestGetPageForChunk:
    """测试 chunk 页码查询"""

    def test_no_mapping_file(self, tmp_path):
        """测试映射文件不存在"""
        # 需要 mock settings.working_dir
        with patch('app.rag_engine.settings') as mock_settings:
            mock_settings.working_dir = tmp_path
            result = RAGEngine._get_page_for_chunk("chunk-123")
            assert result is None

    def test_with_mapping_file(self, tmp_path):
        """测试有映射文件且 chunk 存在"""
        import json
        
        mapping = {
            "chunk-123": {"pages": [1, 2], "file_path": "test.pdf"},
            "chunk-456": {"pages": [3], "file_path": "test.pdf"},
        }
        
        mapping_file = tmp_path / "chunk_page_map.json"
        with open(mapping_file, "w") as f:
            json.dump(mapping, f)

        with patch('app.rag_engine.settings') as mock_settings:
            mock_settings.working_dir = tmp_path
            result = RAGEngine._get_page_for_chunk("chunk-123")
            assert result is not None
            assert result["pages"] == [1, 2]

    def test_chunk_not_in_mapping(self, tmp_path):
        """测试 chunk ID 不在映射中"""
        import json
        
        mapping = {
            "chunk-123": {"pages": [1, 2], "file_path": "test.pdf"},
        }
        
        mapping_file = tmp_path / "chunk_page_map.json"
        with open(mapping_file, "w") as f:
            json.dump(mapping, f)

        with patch('app.rag_engine.settings') as mock_settings:
            mock_settings.working_dir = tmp_path
            result = RAGEngine._get_page_for_chunk("chunk-999")
            assert result is None
