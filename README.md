<<<<<<< HEAD
# 智学 (ZhiXue) - Obsidian AI 知识助手

智学是一个为 Obsidian 打造的专属 AI RAG 知识助手。支持本地 Ollama 与 SiliconFlow 云端大模型，结合 LightRAG 图算法挖掘个人笔记。

## 🛠️ 安装与部署指南

### 1. 编译前端插件
`bash
# 将代码放入 YourVault/.obsidian/plugins/zhixue
cd YourVault/.obsidian/plugins/zhixue
npm install
npm run build
`

### 2. 部署 Python 后台环境
建议使用 Python 虚拟环境：
`bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
`

### 3. 配置与使用
1. 在 Obsidian 开启插件。
2. 在插件设置中配置大模型 API Key（会自动同步）。
3. 通过侧边栏开始提问！

## ⚠️ 隐私提醒
已配置 .gitignore。请注意不要把个人的 data.json、backend/.env 以及 _zhixue/ 数据目录上传至公开代码库！
=======
# ---obsidian-rag-
一款obsidian的ai插件，后端采用rag-anything，采用fastapi封装，前端用typescirpt开发
>>>>>>>
