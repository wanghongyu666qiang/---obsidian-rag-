"""
智学 (ZhiXue) - RAG 引擎封装
基于 RAG-Anything + LightRAG + Ollama

重型依赖（raganything、lightrag、torch 等）采用延迟加载策略：
只在首次需要 RAG 功能时才 import，避免拖慢服务器启动速度。
"""
import asyncio
import json
import logging
import re
import threading
from pathlib import Path
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)

# 延迟加载的模块引用（在 initialize() 中赋值）
_RAGAnything = None
_RAGAnythingConfig = None
_openai_complete_if_cache = None
_openai_embed = None
_EmbeddingFunc = None


def _import_heavy_deps():
    """延迟导入重型依赖，首次调用时加载"""
    global _RAGAnything, _RAGAnythingConfig
    global _openai_complete_if_cache, _openai_embed, _EmbeddingFunc

    if _RAGAnything is not None:
        return

    logger.info("正在加载 RAG 依赖（首次加载可能需要几秒）...")
    from lightrag.llm.openai import openai_complete_if_cache, openai_embed
    from lightrag.utils import EmbeddingFunc
    from raganything import RAGAnything, RAGAnythingConfig

    _openai_complete_if_cache = openai_complete_if_cache
    _openai_embed = openai_embed
    _EmbeddingFunc = EmbeddingFunc
    _RAGAnything = RAGAnything
    _RAGAnythingConfig = RAGAnythingConfig
    logger.info("RAG 依赖加载完成")


class RAGEngine:
    """封装 RAG-Anything，管理文档摄取和查询"""

    def __init__(self):
        self.rag: Optional[object] = None
        self._initialized = False
        self._initializing = False
        self._indexing = False
        self._indexed_files: set = set()
        self._init_error: Optional[str] = None
        # 进度追踪（供前端轮询）
        self._ingest_progress: dict = {}

    def _write_model_info(self):
        """将当前 Embedding 模型信息写入 working_dir/model_info.json"""
        import json
        info = {
            "embedding_model": settings.final_embedding_model,
            "embedding_dim": settings.final_embedding_dim,
            "created_at": __import__("datetime").datetime.now().isoformat(),
        }
        info_path = settings.working_dir / "model_info.json"
        try:
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
            logger.info(f"已写入模型信息: {info['embedding_model']} (dim={info['embedding_dim']})")
        except Exception as e:
            logger.warning(f"写入 model_info.json 失败: {e}")

    async def _migrate_old_index_if_needed(self):
        """从旧版 rag_storage/ 根目录迁移索引文件到模型专属子目录（仅首次）"""
        import json, shutil
        old_dir = settings.working_dir.parent   # rag_storage/
        new_dir = settings.working_dir           # rag_storage/<model>/

        # 旧目录不存在，无需迁移
        if not old_dir.exists():
            return

        # 新目录已有文件，跳过迁移
        new_json_files = list(new_dir.glob("*.json"))
        if new_json_files:
            return

        # 检查旧目录是否有 model_info.json（记录当初用的哪个模型）
        old_info_path = old_dir / "model_info.json"
        if old_info_path.exists():
            try:
                with open(old_info_path, "r", encoding="utf-8") as f:
                    old_info = json.load(f)
                old_model = old_info.get("embedding_model", "")
                current_model = settings.final_embedding_model
                if old_model and old_model != current_model:
                    logger.info(
                        f"旧索引模型 ({old_model}) 与当前模型 ({current_model}) 不同，跳过自动迁移。"
                        f"如需使用旧索引，请手动复制 rag_storage/ 下的 .json 文件到 {new_dir}"
                    )
                    return
            except Exception as e:
                logger.warning(f"读取旧 model_info.json 失败: {e}")

        # 旧目录有索引文件才迁移（排除 model_info.json 和 chunk_page_map.json）
        old_json_files = list(old_dir.glob("*.json"))
        # 过滤掉不该迁移的文件
        exclude_files = {"model_info.json", "chunk_page_map.json"}
        old_json_files = [f for f in old_json_files if f.name not in exclude_files]
        if not old_json_files:
            return

        logger.info(f"检测到旧版索引文件，正在迁移到 {new_dir} ...")
        migrated = 0
        for f in old_json_files:
            try:
                shutil.copy2(f, new_dir / f.name)
                migrated += 1
            except Exception as e:
                logger.warning(f"迁移文件失败 {f.name}: {e}")
        logger.info(f"索引迁移完成，共迁移 {migrated} 个文件")

    async def initialize(self):
        """初始化 RAGAnything 实例（延迟加载重型依赖）"""
        if self._initialized:
            return
        if self._initializing:
            # 等待另一个线程完成初始化
            while self._initializing:
                await asyncio.sleep(0.2)
            if self._initialized:
                return
            raise RuntimeError(f"RAG 初始化失败: {self._init_error}")

        self._initializing = True
        try:
            # 在后台线程中加载重型依赖（避免阻塞事件循环）
            await asyncio.get_event_loop().run_in_executor(None, _import_heavy_deps)

            logger.info("正在初始化 RAG 引擎...")

            # 确保工作目录存在
            settings.working_dir.mkdir(parents=True, exist_ok=True)

            # 多模型索引隔离：首次切换到新模型时，从旧目录迁移索引文件
            await self._migrate_old_index_if_needed()

            # LLM 函数（闭包：每次调用时读取最新 settings）
            # 使用 active_llm_base_url/active_llm_api_key，可与 Embedding 分开配置
            def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
                return _openai_complete_if_cache(
                    settings.LLM_MODEL,
                    prompt,
                    system_prompt=system_prompt,
                    history_messages=history_messages,
                    api_key=settings.active_llm_api_key,
                    base_url=settings.active_llm_base_url,
                    **kwargs,
                )

            # Vision 函数（同样使用 LLM 独立配置）
            def vision_model_func(
                prompt, system_prompt=None, history_messages=[], image_data=None, messages=None, **kwargs
            ):
                if messages:
                    return _openai_complete_if_cache(
                        settings.LLM_MODEL,
                        "",
                        system_prompt=None,
                        history_messages=[],
                        messages=messages,
                        api_key=settings.active_llm_api_key,
                        base_url=settings.active_llm_base_url,
                        **kwargs,
                    )
                elif image_data:
                    return _openai_complete_if_cache(
                        settings.LLM_MODEL,
                        "",
                        system_prompt=None,
                        history_messages=[],
                        messages=[
                            {"role": "system", "content": system_prompt} if system_prompt else None,
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{image_data}"
                                        },
                                    },
                                ],
                            } if image_data else {"role": "user", "content": prompt},
                        ],
                        api_key=settings.active_llm_api_key,
                        base_url=settings.active_llm_base_url,
                        **kwargs,
                    )
                else:
                    return llm_model_func(prompt, system_prompt, history_messages, **kwargs)

            # Embedding 函数（使用 final_embedding_* 属性，支持自动选择 + 手动覆盖）
            embedding_func = _EmbeddingFunc(
                embedding_dim=settings.final_embedding_dim,
                max_token_size=8192,
                func=lambda texts: _openai_embed.func(
                    texts,
                    model=settings.final_embedding_model,
                    api_key=settings.final_embedding_api_key,
                    base_url=settings.final_embedding_base_url,
                ),
            )

            # RAGAnything 配置
            config = _RAGAnythingConfig(
                working_dir=str(settings.working_dir),
                parser=settings.PARSER,
                parse_method=settings.PARSE_METHOD,
                enable_image_processing=settings.ENABLE_IMAGE_PROCESSING,
                enable_table_processing=settings.ENABLE_TABLE_PROCESSING,
                enable_equation_processing=settings.ENABLE_EQUATION_PROCESSING,
            )

            # LightRAG 参数调优：更精细分块，增加候选数量
            lightrag_kwargs = {
                "chunk_token_size": settings.CHUNK_SIZE,
                "chunk_overlap_token_size": settings.CHUNK_OVERLAP,
            }

            # 初始化 RAGAnything
            self.rag = _RAGAnything(
                config=config,
                llm_model_func=llm_model_func,
                vision_model_func=vision_model_func,
                embedding_func=embedding_func,
                lightrag_kwargs=lightrag_kwargs,
            )

            self._initialized = True
            self._init_error = None

            # 记录当前模型信息，方便判断索引兼容性
            self._write_model_info()

            logger.info("RAG 引擎初始化完成")

        except Exception as e:
            self._init_error = str(e)
            logger.error(f"RAG 引擎初始化失败: {e}")
            raise
        finally:
            self._initializing = False

    async def initialize_background(self):
        """后台初始化（不阻塞调用者），失败只记日志不抛异常"""
        try:
            await self.initialize()
        except Exception as e:
            logger.warning(f"RAG 后台初始化失败: {e}")

    async def ingest_file(self, file_path: str) -> dict:
        """摄取单个文件"""
        if not self._initialized:
            await self.initialize()

        path = Path(file_path)
        if not path.exists():
            return {"status": "error", "message": f"文件不存在: {file_path}"}

        try:
            if path.suffix.lower() == ".md":
                content = path.read_text(encoding="utf-8")
                content_list = [
                    {"type": "text", "text": content, "page_idx": 0}
                ]
                await self.rag.insert_content_list(
                    content_list=content_list,
                    file_path=str(path),
                    display_stats=True,
                )
            else:
                await self.rag.process_document_complete(
                    file_path=str(path),
                    output_dir=str(settings.working_dir / "output"),
                )

            self._indexed_files.add(str(path))
            return {"status": "success", "file": str(path)}

        except Exception as e:
            logger.error(f"摄取文件失败 {file_path}: {e}")
            return {"status": "error", "message": str(e)}

    async def ingest_vault(self, force: bool = False) -> dict:
        """摄取整个 Vault 的 Markdown 和 PDF 文件"""
        if not self._initialized:
            await self.initialize()

        if self._indexing:
            return {"status": "busy", "message": "正在索引中，请稍后"}

        self._indexing = True
        # 初始化进度
        self._ingest_progress = {
            "status": "scanning",
            "current_file": "",
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "total": 0,
            "current_phase": "扫描文件中...",
        }
        vault_path = settings.vault_path

        try:
            # 支持 .md 和 .pdf 文件
            all_files = []
            for ext in ("*.md", "*.pdf"):
                all_files.extend(vault_path.rglob(ext))
            all_files = [
                f for f in all_files
                if not str(f).startswith(str(settings.zhixue_dir))
                and not str(f).startswith(str(vault_path / ".obsidian"))
            ]

            self._ingest_progress["total"] = len(all_files)
            self._ingest_progress["status"] = "indexing"
            self._ingest_progress["current_phase"] = f"开始索引 {len(all_files)} 个文件..."

            # 增量检查：从 kv_store_doc_status.json 读取已处理文件
            doc_status_path = settings.working_dir / "kv_store_doc_status.json"
            already_processed: set = set()
            if not force and doc_status_path.exists():
                try:
                    with open(doc_status_path, "r", encoding="utf-8") as f:
                        doc_status = json.load(f)
                    for doc_info in doc_status.values():
                        if isinstance(doc_info, dict) and doc_info.get("status") == "processed":
                            fp = doc_info.get("file_path", "")
                            if fp:
                                # 构造完整路径匹配
                                already_processed.add(fp)
                                already_processed.add(str(vault_path / fp))
                except Exception as e:
                    logger.warning(f"读取 doc_status 失败，跳过增量检查: {e}")

            processed = 0
            errors = 0
            skipped = 0
            total = len(all_files)

            for i, f in enumerate(all_files):
                # 更新进度
                self._ingest_progress["current_file"] = f.name
                self._ingest_progress["current_phase"] = f"处理中 ({i+1}/{total})"

                # 增量：跳过已处理文件
                if not force:
                    if str(f) in self._indexed_files:
                        skipped += 1
                        self._ingest_progress["skipped"] = skipped
                        continue
                    if f.name in already_processed or str(f) in already_processed:
                        self._indexed_files.add(str(f))
                        skipped += 1
                        self._ingest_progress["skipped"] = skipped
                        continue

                logger.info(f"[Ingest] 处理文件 ({processed + skipped + errors + 1}/{total}): {f.name}")
                result = await self.ingest_file(str(f))
                if result["status"] == "success":
                    processed += 1
                    self._ingest_progress["processed"] = processed
                    # PDF 文件处理完成后，尝试构建页码映射
                    if f.suffix.lower() == ".pdf":
                        try:
                            await self._build_chunk_page_map(str(f))
                        except Exception as map_err:
                            logger.warning(f"构建页码映射失败 ({f.name}): {map_err}")
                else:
                    errors += 1
                    self._ingest_progress["errors"] = errors
                    logger.error(f"摄取文件失败: {f.name} - {result.get('message', '')}")

            # 完成
            self._ingest_progress["status"] = "done"
            self._ingest_progress["current_phase"] = f"索引完成：处理 {processed} 个，跳过 {skipped} 个，失败 {errors} 个"

            return {
                "status": "success",
                "files_processed": processed,
                "files_skipped": skipped,
                "errors": errors,
                "total_files": total,
            }

        except Exception as e:
            logger.error(f"全量摄取失败: {e}")
            self._ingest_progress["status"] = "error"
            self._ingest_progress["current_phase"] = f"索引失败: {str(e)[:100]}"
            return {"status": "error", "message": str(e)}
        finally:
            self._indexing = False

    async def query(self, question: str, mode: str = "hybrid", timeout: int = 300) -> dict:
        """查询知识库

        Args:
            question: 查询问题
            mode: 查询模式 (hybrid/local/global/naive)
            timeout: 超时秒数（deepseek-r1 等思考模型需要较长时间）
        """
        # 检查初始化状态
        if not self._initialized and not self._initializing:
            # 从未初始化也从未尝试过 → 初始化
            try:
                await self.initialize()
            except Exception as e:
                return {"status": "error", "error_type": "init_error", "message": f"RAG 引擎初始化失败: {e}"}
        elif self._initializing:
            # 正在后台初始化中，等待（最多 60 秒）
            waited = 0
            while self._initializing and waited < 60:
                await asyncio.sleep(1)
                waited += 1
            if self._initializing:
                return {"status": "error", "error_type": "init_timeout", "message": "RAG 引擎正在初始化中，请稍后再试"}
            if not self._initialized:
                return {"status": "error", "error_type": "init_error", "message": f"RAG 引擎初始化失败: {self._init_error}"}
        elif self._init_error:
            # 之前初始化失败过，且有缓存的错误信息
            return {"status": "error", "error_type": "init_error", "message": f"RAG 引擎不可用: {self._init_error}"}

        try:
            # 确保 LightRAG 实例已创建（RAGAnything 的 aquery 不会自动初始化 lightrag）
            ensure_result = await self.rag._ensure_lightrag_initialized()
            if isinstance(ensure_result, dict) and not ensure_result.get("success"):
                error_msg = ensure_result.get("error", "LightRAG 初始化失败")
                return {"status": "error", "error_type": "init_error", "message": error_msg}

            # 调试：检查 LightRAG 内部状态
            lightrag = self.rag.lightrag
            if lightrag:
                try:
                    entity_count = lightrag.entities_vdb.collection.count() if lightrag.entities_vdb else -1
                    chunk_count = lightrag.text_chunks.collected_data.qsize() if lightrag.text_chunks else -1
                    logger.info(f"[RAG调试] LightRAG 状态: entities_vdb={'有' if lightrag.entities_vdb else '无'}, "
                               f"text_chunks={'有' if lightrag.text_chunks else '无'}")
                except Exception as debug_e:
                    logger.info(f"[RAG调试] LightRAG 状态检查失败: {debug_e}")

            logger.info(f"[RAG调试] 开始查询: question='{question[:100]}', mode={mode}")

            # 直接调用 LightRAG.aquery_llm() 以获取结构化结果（含检索上下文）
            # RAGAnything.aquery() 只返回 LLM 回答，会丢失上下文信息
            from lightrag import QueryParam
            query_param = QueryParam(mode=mode)
            query_param.stream = False  # 强制非流式，确保拿到完整结构化结果
            llm_result = await lightrag.aquery_llm(question, param=query_param)

            # 从结构化结果里提取回答和上下文
            llm_response = llm_result.get("llm_response", {})
            data = llm_result.get("data", {})
            metadata = llm_result.get("metadata", {})

            logger.info(f"[RAG调试] aquery_llm 返回结构: status={llm_result.get('status')}, "
                       f"llm_response 类型={type(llm_response)}, "
                       f"llm_response.content 长度={len(str(llm_response.get('content', '')))}, "
                       f"data 类型={type(data)}, "
                       f"metadata={metadata}")

            if llm_result.get("status") == "failure":
                # 查询失败（如没有检索到任何结果）→ 直接调用纯 LLM，绕过 LightRAG 的 prompt 模板
                failure_reason = metadata.get("failure_reason", "unknown")
                logger.warning(f"[RAG调试] 查询返回空结果: reason={failure_reason}，回退到纯 LLM")
                try:
                    raw_answer = await self._raw_llm_chat(question)
                    answer = self._filter_thinking_tags(raw_answer)
                except Exception as e:
                    import traceback
                    logger.warning(f"[RAG调试] 纯 LLM 回退失败: {e}\n{traceback.format_exc()}")
                    # 如果纯 LLM 也失败，尝试用 LightRAG 给的 fallback
                    fallback_content = ""
                    if isinstance(llm_response, dict):
                        fallback_content = llm_response.get("content") or ""
                    answer = fallback_content or "（知识库中未找到相关内容，AI 也无法生成回答）"

                return {
                    "status": "success",
                    "answer": answer,
                    "mode": mode,
                    "context_used": False,
                    "retrieved_entities": [],
                    "retrieved_chunks": [],
                }

            # 防御性提取：确保 content 不会是 None
            raw_content = ""
            if isinstance(llm_response, dict):
                if not llm_response.get("is_streaming"):
                    raw_content = llm_response.get("content") or ""
            answer = self._filter_thinking_tags(raw_content)

            # 从 data 中提取来源、实体、文本块
            # LightRAG aquery_llm 返回的数据结构：
            # data = { 'entities': [...], 'relationships': [...], 'chunks': [...], 'references': [{reference_id, file_path}] }
            sources = []
            retrieved_entities = []
            retrieved_chunks = []
            context_used = True

            if isinstance(data, dict):
                # 来源：从 chunks 中提取前3个最相关的文件（含页码信息）
                # chunks 按相关性排序
                chunks = data.get("chunks", [])
                seen = set()
                for chunk in chunks:
                    if isinstance(chunk, dict) and "file_path" in chunk:
                        fp = chunk["file_path"]
                        if fp and fp not in seen and len(sources) < 3:
                            # 尝试获取页码信息
                            chunk_id = chunk.get("chunk_id") or chunk.get("reference_id") or ""
                            page_info = self._get_page_for_chunk(chunk_id) if chunk_id else None

                            source_entry = {
                                "file_path": fp,
                                "page": page_info.get("pages") if page_info else None,
                                "excerpt": (chunk.get("content", "") or "")[:100].strip(),
                            }
                            # 页码信息缺失时，添加友好提示
                            if not page_info:
                                source_entry["note"] = f"见文件: {Path(fp).name}"

                            sources.append(source_entry)
                            seen.add(fp)

                # 实体：key 是 'entities' 而不是 'retrieved_entities'
                retrieved_entities = data.get("entities", [])
                if not retrieved_entities:
                    # 兼容旧格式
                    retrieved_entities = data.get("retrieved_entities", [])

                # 文本块：key 是 'chunks' 而不是 'retrieved_chunks'
                retrieved_chunks = data.get("chunks", [])
                if not retrieved_chunks:
                    # 兼容旧格式
                    retrieved_chunks = data.get("retrieved_chunks", [])

            logger.info(f"[RAG调试] 查询成功: sources={sources}, 实体数={len(retrieved_entities)}, 文本块数={len(retrieved_chunks)}")

            # 如果知识库没有检索到相关内容，回退到纯 LLM 回答
            if "[no-context]" in (answer or "") or not retrieved_chunks:
                logger.info("[RAG调试] 知识库无相关内容，回退到纯 LLM 回答")
                try:
                    raw_answer = await self._raw_llm_chat(question)
                    answer = self._filter_thinking_tags(raw_answer)
                    context_used = False
                    sources = []
                except Exception as e:
                    logger.warning(f"[RAG调试] 纯 LLM 回退失败: {e}")
                    answer = (answer or "").replace("[no-context]", "").strip()

            return {
                "status": "success",
                "answer": answer or "（模型未返回有效内容）",
                "sources": sources,  # 新增：来源文件列表
                "mode": mode,
                "context_used": context_used,
                "retrieved_entities": retrieved_entities[:10],
                "retrieved_chunks": retrieved_chunks[:5],
            }
        except asyncio.TimeoutError:
            logger.error(f"查询超时 ({timeout}s): {question[:50]}...")
            return {"status": "error", "error_type": "timeout", "message": f"查询超时（{timeout}秒），模型推理时间过长，请尝试更简单的问题或更换更快的模型"}
        except ConnectionError as e:
            logger.error(f"无法连接 Ollama: {e}")
            return {"status": "error", "error_type": "ollama_connection", "message": f"无法连接 Ollama，请确认 Ollama 是否正在运行"}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"查询失败: {error_msg}")

            # 识别常见错误类型
            lower_msg = error_msg.lower()
            if "Connection" in error_msg or "connect" in lower_msg:
                error_type = "ollama_connection"
                message = "无法连接 Ollama，请确认 Ollama 是否正在运行"
            elif "model" in lower_msg and ("not found" in lower_msg or "pull" in lower_msg):
                error_type = "model_missing"
                message = f"模型未找到，请确认 {settings.LLM_MODEL} 是否已安装（运行 ollama pull {settings.LLM_MODEL}）"
            elif "balance" in lower_msg or "insufficient" in lower_msg:
                error_type = "api_balance"
                message = f"API 账户余额不足: {settings.LLM_MODEL} 需要充值后才能使用"
            elif "disabled" in lower_msg or "model disabled" in lower_msg:
                error_type = "api_model_disabled"
                message = f"API 模型已被禁用: {settings.LLM_MODEL} 在提供商处不可用，请更换其他模型"
            elif "api key" in lower_msg or "unauthorized" in lower_msg or "invalid" in lower_msg:
                error_type = "api_key_invalid"
                message = "API Key 无效或已过期，请检查后重新配置"
            elif "gpu" in lower_msg or "memory" in lower_msg or "cuda" in lower_msg:
                error_type = "resource_error"
                message = "GPU/内存资源不足，请关闭其他程序后重试"
            else:
                error_type = "query_error"
                message = f"查询失败: {error_msg[:200]}"

            return {"status": "error", "error_type": error_type, "message": message}

    async def _raw_llm_chat(self, question: str) -> str:
        """直接调用 LLM API，完全绕过 LightRAG 的 prompt 包装"""
        import httpx

        base_url = settings.active_llm_base_url.rstrip("/")
        api_key = settings.active_llm_api_key
        model = settings.LLM_MODEL

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": question}],
            "temperature": 0.7,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    @staticmethod
    def _filter_thinking_tags(text: str) -> str:
        """过滤 DeepSeek R1 等模型的思考标签"""
        if text is None:
            return ""
        filtered = re.sub(r'💭.*?\n', '', text, flags=re.DOTALL)
        filtered = re.sub(r'\n{3,}', '\n\n', filtered)
        return filtered.strip()

    # ──────────────────────── 页码映射（Phase 2） ────────────────────────

    @staticmethod
    def _find_mineru_content_list(pdf_path: str, output_base_dir: Path) -> Optional[Path]:
        """在 MinerU 输出目录中查找 PDF 对应的 content_list.json 缓存文件。

        RAGAnything 的路径结构:
          output_base_dir / {stem}_{hash} / {stem} / {subdir} / {stem}_content_list.json

        Returns:
            找到的 JSON 文件路径，或 None
        """
        pdf_file = Path(pdf_path).resolve()
        stem = pdf_file.stem

        # 扫描 output_base_dir 下所有 {stem}_* 子目录
        for candidate_dir in output_base_dir.iterdir():
            if not candidate_dir.is_dir():
                continue
            if not candidate_dir.name.startswith(f"{stem}_"):
                continue

            # 在子目录下查找 content_list.json（支持多层嵌套）
            for json_file in candidate_dir.rglob(f"{stem}_content_list.json"):
                return json_file

        return None

    async def _build_chunk_page_map(self, pdf_path: str) -> dict:
        """为 PDF 文件构建 chunk → 页码 的映射。

        读取 MinerU 缓存的 content_list.json，提取每页文本的字符偏移量，
        然后匹配 LightRAG chunk 的内容到对应页码。

        Args:
            pdf_path: PDF 文件的绝对路径
        """
        import hashlib

        pdf_file = Path(pdf_path).resolve()
        stem = pdf_file.stem
        output_base_dir = settings.working_dir / "output"
        chunk_map_path = settings.working_dir / "chunk_page_map.json"

        # 1. 查找 MinerU 缓存的 content_list.json
        content_list_file = self._find_mineru_content_list(pdf_path, output_base_dir)
        if not content_list_file:
            logger.warning(f"未找到 MinerU 缓存文件，跳过页码映射: {stem}")
            return {}

        try:
            with open(content_list_file, "r", encoding="utf-8") as f:
                content_list = json.load(f)
        except Exception as e:
            logger.error(f"读取 MinerU 缓存失败: {e}")
            return {}

        if not isinstance(content_list, list) or len(content_list) == 0:
            logger.warning(f"MinerU content_list 为空: {stem}")
            return {}

        # 2. 构建页码 → 文本映射（累积字符偏移量）
        page_boundaries = []  # [(start_char, end_char, page_idx), ...]
        full_text = ""
        for item in content_list:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type", "")
            page_idx = item.get("page_idx", 0)

            if item_type == "text":
                text = item.get("text", "")
                start = len(full_text)
                full_text += text + "\n"
                end = len(full_text)
                page_boundaries.append((start, end, page_idx))

        if not page_boundaries or len(full_text) < 50:
            logger.warning(f"MinerU 文本内容过少，跳过页码映射: {stem}")
            return {}

        # 3. 读取该 PDF 的所有 chunks
        chunks_path = settings.working_dir / "kv_store_text_chunks.json"
        if not chunks_path.exists():
            logger.warning("kv_store_text_chunks.json 不存在")
            return {}

        try:
            with open(chunks_path, "r", encoding="utf-8") as f:
                all_chunks = json.load(f)
        except Exception as e:
            logger.error(f"读取 chunks 失败: {e}")
            return {}

        # 找到属于该 PDF 的 doc_id
        pdf_name = pdf_file.name
        doc_status_path = settings.working_dir / "kv_store_doc_status.json"
        target_doc_ids = set()
        if doc_status_path.exists():
            try:
                with open(doc_status_path, "r", encoding="utf-8") as f:
                    doc_status = json.load(f)
                for doc_id, info in doc_status.items():
                    if isinstance(info, dict) and info.get("file_path") == pdf_name:
                        target_doc_ids.add(doc_id)
            except Exception:
                pass

        if not target_doc_ids:
            logger.warning(f"未在 doc_status 中找到 PDF 的 doc_id: {pdf_name}")
            return {}

        # 4. 匹配每个 chunk 到页码（多重锚点策略，提高可靠性）
        mapping = {}
        for chunk_id, chunk_data in all_chunks.items():
            if not isinstance(chunk_data, dict):
                continue
            if chunk_data.get("full_doc_id") not in target_doc_ids:
                continue

            content = chunk_data.get("content", "")
            if len(content) < 20:
                continue

            # 归一化：去除多余空白，便于匹配
            norm_content = re.sub(r'\s+', ' ', content.strip())
            norm_full = re.sub(r'\s+', ' ', full_text.strip())

            # 多重锚点：尝试在 chunk 的开头、中间、结尾取片段匹配
            pos = -1
            anchors = []
            if len(norm_content) > 40:
                anchors.append(norm_content[:80])
                anchors.append(norm_content[-80:])
            if len(norm_content) > 160:
                mid = len(norm_content) // 2
                anchors.append(norm_content[mid:mid+80])
            # 也尝试前 40 字符（较短但更可能唯一）
            if len(norm_content) >= 40:
                anchors.append(norm_content[:40])

            for anchor in anchors:
                idx = norm_full.find(anchor)
                if idx >= 0:
                    pos = idx
                    break

            if pos < 0:
                # 全部锚点都失败，跳过该 chunk
                logger.debug(f"chunk {chunk_id} 无法在原文中定位，跳过页码映射")
                continue

            # 根据位置确定页码范围
            pages = set()
            for start, end, page_idx in page_boundaries:
                if pos < end and (pos + len(content)) > start:
                    pages.add(page_idx)
            if pages:
                mapping[chunk_id] = {
                    "pages": sorted(pages),
                    "file_path": pdf_name,
                }

        # 5. 保存/更新映射文件（先清理该 PDF 的旧条目，避免脏数据）
        existing_map = {}
        if chunk_map_path.exists():
            try:
                with open(chunk_map_path, "r", encoding="utf-8") as f:
                    existing_map = json.load(f)
            except Exception:
                existing_map = {}

        # 删除该 PDF 已有的旧映射
        to_remove = [k for k, v in existing_map.items() if v.get("file_path") == pdf_name]
        for k in to_remove:
            del existing_map[k]
        if to_remove:
            logger.info(f"清理旧映射: 删除 {pdf_name} 的 {len(to_remove)} 条旧记录")

        existing_map.update(mapping)

        with open(chunk_map_path, "w", encoding="utf-8") as f:
            json.dump(existing_map, f, ensure_ascii=False, indent=2)

        logger.info(f"页码映射构建完成: {stem} -> {len(mapping)} 个 chunks 映射到页码")
        return mapping

    @staticmethod
    def _get_page_for_chunk(chunk_id: str) -> Optional[dict]:
        """查询 chunk 对应的页码信息。

        Args:
            chunk_id: chunk 的 ID（如 "chunk-abc123"）

        Returns:
            {"pages": [3, 4], "file_path": "xxx.pdf"} 或 None
        """
        chunk_map_path = settings.working_dir / "chunk_page_map.json"
        if not chunk_map_path.exists():
            return None

        try:
            with open(chunk_map_path, "r", encoding="utf-8") as f:
                page_map = json.load(f)
            return page_map.get(chunk_id)
        except Exception:
            return None

    async def get_status(self) -> dict:
        """获取引擎状态（含索引进度）"""
        return {
            "initialized": self._initialized,
            "initializing": self._initializing,
            "init_error": self._init_error,
            "indexing": self._indexing,
            "indexed_files": len(self._indexed_files),
            "working_dir": str(settings.working_dir),
            "llm_model": settings.LLM_MODEL,
            "embedding_model": settings.EMBEDDING_MODEL,
            "ingest_progress": self._ingest_progress if self._indexing else {},
        }


# 全局单例
rag_engine = RAGEngine()
