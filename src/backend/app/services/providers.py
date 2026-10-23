from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import settings
from app.services.storage import embed_text


class ProviderGateway:
    """统一封装 OpenAI-compatible API、Ollama 与离线 Mock。"""

    def __init__(self) -> None:
        self.providers = {
            "openai": (settings.openai_base_url, settings.openai_api_key, "gpt-4o-mini"),
            "qwen": (settings.qwen_base_url, settings.qwen_api_key, "qwen-plus"),
            "deepseek": (settings.deepseek_base_url, settings.deepseek_api_key, "deepseek-chat"),
            "glm": (settings.glm_base_url, settings.glm_api_key, "glm-4-flash"),
            "siliconflow": (settings.siliconflow_base_url, settings.siliconflow_api_key, "Qwen/Qwen2.5-72B-Instruct"),
            "ollama": (settings.ollama_base_url, "ollama" if settings.ollama_enabled else "", "qwen2.5:7b"),
        }

    def models(self) -> list[dict[str, Any]]:
        """返回后端允许前端选择的模型；不会泄露 API Key。"""
        models: list[dict[str, Any]] = [
            {
                "id": "mock-chat",
                "provider": "mock",
                "name": "Mock Demo Chat",
                "capabilities": ["chat", "stream", "tools"],
                "enabled": True,
            }
        ]
        for provider, (_base_url, key, model) in self.providers.items():
            if key:
                models.append(
                    {
                        "id": f"{provider}-chat",
                        "provider": provider,
                        "name": model,
                        "capabilities": ["chat", "stream", "tools"],
                        "enabled": True,
                    }
                )
        models.append(
            {
                "id": "local-embedding",
                "provider": "local",
                "name": "Deterministic Demo Embedding",
                "capabilities": ["embedding"],
                "enabled": True,
            }
        )
        if settings.openai_api_key:
            models.append(
                {
                    "id": "text-embedding-3-small",
                    "provider": "openai",
                    "name": "text-embedding-3-small",
                    "capabilities": ["embedding"],
                    "enabled": True,
                }
            )
        return models

    def enabled_model_ids(self, capability: str) -> set[str]:
        """只允许调用由后端环境变量启用且具备指定能力的模型。"""
        return {
            model["id"]
            for model in self.models()
            if model.get("enabled", False) and capability in model["capabilities"]
        }

    async def stream_chat(self, model_id: str, system: str, user: str) -> AsyncIterator[str]:
        # AI TECH STACK: LLM CALL
        if model_id == "mock-chat":
            answer = self._mock_answer(user)
            for word in answer.split(" "):
                await asyncio.sleep(0.012)
                yield word + " "
            return

        provider = model_id.removesuffix("-chat")
        base_url, api_key, model = self.providers.get(provider, ("", "", ""))
        if not api_key:
            yield "当前模型未配置后端 API Key，已切换为演示回答。"
            return
        headers = {"Content-Type": "application/json"}
        if api_key != "ollama":
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "stream": True,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST",
                    f"{base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line.removeprefix("data:").strip()
                        if data == "[DONE]":
                            break
                        try:
                            delta = json.loads(data)["choices"][0].get("delta", {}).get("content", "")
                        except (KeyError, IndexError, json.JSONDecodeError):
                            delta = ""
                        if delta:
                            yield delta
        except (httpx.HTTPError, OSError):
            yield "模型服务暂时不可用，已保留检索与工具证据，请稍后重试或切换 Mock 模型。"

    async def embed(self, model_id: str, text: str) -> list[float]:
        # AI TECH STACK: LLM CALL
        # MVP 的云端 Embedding 入口与模型选择已打通；离线演示使用确定性向量。
        # 生产环境可在此调用 OpenAI-compatible /embeddings，并将维度与 migration 对齐。
        if model_id == "local-embedding" or not model_id:
            return embed_text(text)
        return embed_text(text)

    @staticmethod
    def _mock_answer(prompt: str) -> str:
        if "证据不足" in prompt:
            return "根据当前授权知识库，检索证据不足，无法可靠回答。请补充相关技术文档、日志或代码上下文。"
        return "基于当前授权知识库和工具检查结果：建议先核对报错字段、输入类型和运行环境，再结合引用片段逐项验证。若需要修改代码，请先查看生成的 Patch 预览并完成人工确认。"
