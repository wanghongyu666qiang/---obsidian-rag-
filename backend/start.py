"""
智学 (ZhiXue) 后端启动脚本
用法: python start.py --vault /path/to/vault --port 18765
"""
import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="智学 (ZhiXue) 后端服务")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=18765, help="监听端口")
    parser.add_argument("--vault", default="", help="Obsidian Vault 路径")
    parser.add_argument("--reload", action="store_true", help="开发模式（热重载）")
    args = parser.parse_args()

    # 必须在 import app 之前设置环境变量，确保 config.py 能读到
    if args.vault:
        os.environ["ZHIXUE_VAULT_PATH"] = args.vault
    if args.port:
        os.environ["ZHIXUE_PORT"] = str(args.port)

    # 延迟 import，确保环境变量已设置
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
