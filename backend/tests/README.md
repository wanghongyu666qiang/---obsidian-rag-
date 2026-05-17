# 智学 (ZhiXue) 后端测试

## 安装测试依赖

```bash
pip install -r requirements.txt
```

## 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_config.py
pytest tests/test_rag_engine.py

# 带覆盖率的测试
pytest --cov=app --cov-report=html

# 详细输出
pytest -v
```

## 测试结构

```
tests/
├── __init__.py      # 测试配置
├── conftest.py      # 公共 fixtures
├── test_config.py   # 配置校验测试
└── test_rag_engine.py  # RAG 引擎独立功能测试
```

## 注意事项

- `test_rag_engine.py` 使用 mock 避免加载重型依赖（lightrag, raganything）
- 集成测试需要真实环境（Ollama、Vault 路径等），当前为基础单元测试
- 运行测试前确保后端依赖已安装：`pip install -r requirements.txt`
