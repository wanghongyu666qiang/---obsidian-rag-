"""
测试配置和公共工具
"""
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture
def client():
    """FastAPI 测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_settings():
    """模拟配置（避免依赖真实环境）"""
    # 保存原始值
    original_vault_path = settings.VAULT_PATH
    original_llm_model = settings.LLM_MODEL

    yield settings

    # 恢复原始值
    settings.VAULT_PATH = original_vault_path
    settings.LLM_MODEL = original_llm_model
    settings.invalidate_embedding_cache()
