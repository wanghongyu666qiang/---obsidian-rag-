"""
智学 (ZhiXue) - 环境检查脚本
在首次运行前检查 Ollama、模型、Python 依赖是否就绪

用法: python check_env.py
"""
import sys
import subprocess


def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python 版本过低: {version.major}.{version.minor}.{version.micro}，需要 3.9+")
        return False


def check_ollama_running():
    """检查 Ollama 是否运行"""
    try:
        import httpx
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            print("✅ Ollama 正在运行")
            return True, resp.json()
        else:
            print("❌ Ollama 返回异常状态码")
            return False, None
    except Exception:
        print("❌ Ollama 未运行，请先启动 Ollama")
        print("   启动方式: 在终端输入 ollama serve")
        return False, None


def check_model_installed(models_data, model_name, model_type):
    """检查指定模型是否已安装"""
    if models_data is None:
        return False

    installed = [m.get("name", "").split(":")[0] for m in models_data.get("models", [])]

    if model_name in installed:
        print(f"✅ {model_type} 模型 {model_name} 已安装")
        return True
    else:
        print(f"❌ {model_type} 模型 {model_name} 未安装")
        print(f"   安装方式: ollama pull {model_name}")
        return False


def check_dependencies():
    """检查 Python 依赖"""
    missing = []
    try:
        import fastapi
        print("✅ fastapi 已安装")
    except ImportError:
        print("❌ fastapi 未安装")
        missing.append("fastapi")

    try:
        import uvicorn
        print("✅ uvicorn 已安装")
    except ImportError:
        print("❌ uvicorn 未安装")
        missing.append("uvicorn")

    try:
        import httpx
        print("✅ httpx 已安装")
    except ImportError:
        print("❌ httpx 未安装")
        missing.append("httpx")

    try:
        import raganything
        print("✅ raganything 已安装")
    except ImportError:
        print("❌ raganything 未安装（核心依赖）")
        missing.append("raganything[all]")

    return missing


def main():
    print("=" * 50)
    print("  智学 (ZhiXue) 环境检查")
    print("=" * 50)
    print()

    all_ok = True

    # 1. Python 版本
    print("── Python 版本 ──")
    if not check_python_version():
        all_ok = False
    print()

    # 2. Ollama
    print("── Ollama 服务 ──")
    ollama_ok, models_data = check_ollama_running()
    if not ollama_ok:
        all_ok = False
    print()

    # 3. 模型检查
    if ollama_ok:
        print("── 模型检查 ──")
        # 读取配置
        try:
            from app.config import settings
            llm_model = settings.LLM_MODEL
            emb_model = settings.EMBEDDING_MODEL
        except Exception:
            llm_model = "deepseek-r1"
            emb_model = "nomic-embed-text"

        if not check_model_installed(models_data, llm_model, "LLM"):
            all_ok = False
        if not check_model_installed(models_data, emb_model, "Embedding"):
            all_ok = False
        print()

    # 4. Python 依赖
    print("── Python 依赖 ──")
    missing = check_dependencies()
    if missing:
        all_ok = False
        print()
        print(f"💡 安装缺失依赖: pip install {' '.join(missing)}")
    print()

    # 总结
    print("=" * 50)
    if all_ok:
        print("🎉 所有环境检查通过！可以启动智学了")
        print("   启动方式: python start.py --vault /path/to/your/vault")
    else:
        print("⚠️  部分检查未通过，请按照上述提示修复后重试")
    print("=" * 50)


if __name__ == "__main__":
    main()
