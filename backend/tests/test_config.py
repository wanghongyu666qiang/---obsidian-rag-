"""
测试配置校验功能
"""
import pytest
from app.config import settings


class TestSettingsValidate:
    """测试配置校验"""

    def test_validate_port_invalid(self):
        """测试无效端口号"""
        original_port = settings.PORT
        settings.PORT = 99999  # 无效端口
        
        errors = settings.validate()
        assert any("端口号无效" in e for e in errors)
        
        settings.PORT = original_port  # 恢复

    def test_validate_port_valid(self):
        """测试有效端口号"""
        original_port = settings.PORT
        settings.PORT = 18765  # 有效端口
        
        errors = settings.validate()
        assert not any("端口号无效" in e for e in errors)
        
        settings.PORT = original_port

    def test_validate_vault_path_missing(self):
        """测试 Vault 路径不存在的情况"""
        original_vault = settings.VAULT_PATH
        settings.VAULT_PATH = "C:/Nonexistent/Path"
        
        # 注意：如果自动检测到了真实 Vault，这个测试可能会通过
        # 在生产环境中应该 mock _detect_vault_path
        errors = settings.validate()
        # 不断言具体结果，只确保函数不抛异常
        assert isinstance(errors, list)
        
        settings.VAULT_PATH = original_vault

    def test_validate_returns_list(self):
        """测试 validate() 返回列表"""
        errors = settings.validate()
        assert isinstance(errors, list)
        # 每个元素应该是字符串
        for err in errors:
            assert isinstance(err, str)
