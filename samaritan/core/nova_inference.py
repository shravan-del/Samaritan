"""
nova_inference.py - NovaLLM class using boto3 bedrock-runtime.

Models:
  - us.amazon.nova-2-lite-v1:0 for chat  (cross-region inference profile)
  - amazon.titan-embed-text-v2:0 for text embeddings (1024-dim, normalize=True)

Supports:
  - sync chat()
  - async chat_stream()
  - embed()
  - embed_async()
  - Tool calls via toolConfig
  - Parse toolUse blocks from responses
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, AsyncIterator, Iterator, Optional

import boto3
import botocore

logger = logging.getLogger(__name__)

CHAT_MODEL_ID = "us.amazon.nova-2-lite-v1:0"
EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBED_OUTPUT_DIM = 1024  # Titan Text Embed v2 output dimension


def _to_nova_content_block(content: Any) -> list[dict]:
    """Convert various content formats to Nova's content block format."""
    if isinstance(content, str):
        return [{"text": content}]
    if isinstance(content, list):
        blocks = []
        for item in content:
            if isinstance(item, str):
                blocks.append({"text": item})
            elif isinstance(item, dict):
                blocks.append(item)
        return blocks
    if isinstance(content, dict):
        return [content]
    return [{"text": str(content)}]


def _convert_messages(messages: list[dict]) -> list[dict]:
    """Convert internal message format to Nova's message format."""
    nova_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Map roles: system handled separately in system prompt
        if role == "system":
            continue

        nova_msg = {
            "role": role,
            "content": _to_nova_content_block(content),
        }
        nova_messages.append(nova_msg)
    return nova_messages


def _extract_system_prompt(messages: list[dict]) -> Optional[list[dict]]:
    """Extract system messages and return as Nova system block."""
    system_texts = [
        msg["content"] for msg in messages if msg.get("role") == "system"
    ]
    if not system_texts:
        return None
    combined = "\n\n".join(system_texts)
    return [{"text": combined}]


def _parse_response(response_body: dict) -> dict:
    """
    Parse Nova response body into a normalized dict:
      {
        "text": str,
        "tool_calls": list[dict],  # each: {id, name, input}
        "stop_reason": str,
        "usage": dict,
      }
    """
    output = response_body.get("output", {})
    message = output.get("message", {})
    content_blocks = message.get("content", [])
    stop_reason = response_body.get("stopReason", "end_turn")
    usage = response_body.get("usage", {})

    text_parts = []
    tool_calls = []

    for block in content_blocks:
        if "text" in block:
            text_parts.append(block["text"])
        if block.get("type") == "tool_use" or "toolUse" in block:
            tool_data = block.get("toolUse", block)
            tool_calls.append(
                {
                    "id": tool_data.get("toolUseId", tool_data.get("id", "")),
                    "name": tool_data.get("name", ""),
                    "input": tool_data.get("input", {}),
                }
            )

    return {
        "text": "\n".join(text_parts),
        "tool_calls": tool_calls,
        "stop_reason": stop_reason,
        "usage": usage,
        "raw": response_body,
    }


class NovaLLM:
    """
    AWS Bedrock Nova LLM client.

    Handles chat inference via us.amazon.nova-2-lite-v1:0
    and text embeddings via amazon.titan-embed-text-v2:0.
    """

    def __init__(
        self,
        region: str = "us-east-1",
        chat_model_id: str = CHAT_MODEL_ID,
        embed_model_id: str = EMBED_MODEL_ID,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ):
        self.region = region
        self.chat_model_id = chat_model_id
        self.embed_model_id = embed_model_id
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p

        self._client = boto3.client(
            "bedrock-runtime",
            region_name=self.region,
        )
        logger.info(
            "NovaLLM initialized | chat=%s embed=%s region=%s",
            self.chat_model_id,
            self.embed_model_id,
            self.region,
        )

    def _build_request_body(
        self,
        messages: list[dict],
        system: Optional[list[dict]] = None,
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[dict] = None,
    ) -> dict:
        body: dict = {
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": self.max_tokens,
                "temperature": self.temperature,
                "topP": self.top_p,
            },
        }
        if system:
            body["system"] = system
        if tools:
            tool_config: dict = {"tools": tools}
            if tool_choice:
                tool_config["toolChoice"] = tool_choice
            body["toolConfig"] = tool_config
        return body

    # ------------------------------------------------------------------ #
    #  Chat (sync)                                                         #
    # ------------------------------------------------------------------ #

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[dict] = None,
    ) -> dict:
        """
        Synchronous chat call.

        Parameters
        ----------
        messages : list of dicts with 'role' and 'content'.
        tools    : Nova toolConfig tools list (optional).
        tool_choice : Nova toolChoice dict (optional).

        Returns parsed response dict.
        """
        system = _extract_system_prompt(messages)
        nova_messages = _convert_messages(messages)
        body = self._build_request_body(
            nova_messages, system=system, tools=tools, tool_choice=tool_choice
        )

        logger.debug("Nova chat request | model=%s msgs=%d", self.chat_model_id, len(nova_messages))

        try:
            response = self._client.invoke_model(
                modelId=self.chat_model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            response_body = json.loads(response["body"].read())
            result = _parse_response(response_body)
            logger.debug("Nova chat response | stop=%s tools=%d", result["stop_reason"], len(result["tool_calls"]))
            return result
        except botocore.exceptions.ClientError as e:
            logger.error("Bedrock ClientError: %s", e)
            raise

    # ------------------------------------------------------------------ #
    #  Chat (async streaming)                                              #
    # ------------------------------------------------------------------ #

    async def chat_stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[dict] = None,
    ) -> AsyncIterator[dict]:
        """
        Async streaming chat call.

        Yields event dicts:
          {"type": "text_delta", "text": str}
          {"type": "tool_use", "tool_call": dict}
          {"type": "done", "stop_reason": str, "usage": dict}
        """
        system = _extract_system_prompt(messages)
        nova_messages = _convert_messages(messages)
        body = self._build_request_body(
            nova_messages, system=system, tools=tools, tool_choice=tool_choice
        )

        loop = asyncio.get_event_loop()

        def _invoke_stream():
            return self._client.invoke_model_with_response_stream(
                modelId=self.chat_model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

        response = await loop.run_in_executor(None, _invoke_stream)
        stream = response.get("body")

        accumulated_tool: dict = {}

        for event in stream:
            chunk = event.get("chunk", {})
            if not chunk:
                continue
            raw = json.loads(chunk.get("bytes", b"{}"))

            # Nova streaming response uses camelCase event keys as top-level keys
            # e.g. {"contentBlockDelta": {"delta": {"text": "..."}, "contentBlockIndex": 0}}
            # NOT {"type": "content_block_delta", ...}

            if "contentBlockDelta" in raw:
                cbd = raw["contentBlockDelta"]
                delta = cbd.get("delta", {})
                if "text" in delta:
                    yield {"type": "text_delta", "text": delta["text"]}
                elif "toolUse" in delta:
                    # streaming tool input JSON
                    accumulated_tool["input_json"] = (
                        accumulated_tool.get("input_json", "") + delta["toolUse"].get("input", "")
                    )

            elif "contentBlockStart" in raw:
                cbs = raw["contentBlockStart"]
                block = cbs.get("start", {})
                if "toolUse" in block:
                    accumulated_tool = {
                        "id": block["toolUse"].get("toolUseId", ""),
                        "name": block["toolUse"].get("name", ""),
                        "input_json": "",
                    }

            elif "contentBlockStop" in raw:
                if accumulated_tool.get("name"):
                    try:
                        tool_input = json.loads(accumulated_tool.get("input_json", "{}") or "{}")
                    except json.JSONDecodeError:
                        tool_input = {}
                    yield {
                        "type": "tool_use",
                        "tool_call": {
                            "id": accumulated_tool.get("id", ""),
                            "name": accumulated_tool.get("name", ""),
                            "input": tool_input,
                        },
                    }
                    accumulated_tool = {}

            elif "messageStop" in raw:
                stop = raw["messageStop"]
                yield {
                    "type": "done",
                    "stop_reason": stop.get("stopReason", "end_turn"),
                    "usage": {},
                }

            elif "metadata" in raw:
                # Final metadata event with usage info — ignored for now
                pass

    # ------------------------------------------------------------------ #
    #  Embeddings (sync)                                                   #
    # ------------------------------------------------------------------ #

    def embed(self, text: str) -> list[float]:
        """
        Generate embedding vector for text using Amazon Titan Text Embed v2.

        Titan Text Embed v2 body format:
          { "inputText": "...", "dimensions": 1024, "normalize": true }

        Returns list of floats (length 1024).
        """
        body = {
            "inputText": text,
            "dimensions": EMBED_OUTPUT_DIM,
            "normalize": True,
        }
        try:
            response = self._client.invoke_model(
                modelId=self.embed_model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(response["body"].read())
            # Titan Text v2 returns: {"embedding": [...], "embeddingsByType": {...}, "inputTextTokenCount": N}
            embedding = result.get("embedding", [])
            logger.debug("Embed | dim=%d", len(embedding))
            return embedding
        except botocore.exceptions.ClientError as e:
            logger.error("Bedrock embed ClientError: %s", e)
            raise

    # ------------------------------------------------------------------ #
    #  Embeddings (async)                                                  #
    # ------------------------------------------------------------------ #

    async def embed_async(self, text: str) -> list[float]:
        """Async wrapper around embed()."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed, text)
