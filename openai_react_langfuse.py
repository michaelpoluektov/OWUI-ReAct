"""
title: OpenAI ReAct with Langfuse
author: Michael Poluektov
author_url: https://github.com/michaelpoluektov
git_url: https://github.com/michaelpoluektov/OWUI-ReAct
description: OpenAI ReAct
required_open_webui_version: 0.3.15
requirements: langchain-openai==0.1.25, langgraph, ollama, langchain_ollama==0.1.3
version: 0.3.1
licence: MIT
"""

import os
from typing import AsyncGenerator, Awaitable, Callable, Optional, Protocol

import ollama
from langchain_core.tools import StructuredTool
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langfuse.callback import CallbackHandler
from langgraph.prebuilt import create_react_agent
from openai import OpenAI
from pydantic import BaseModel, Field

BAD_NAMES = ["202", "13", "3.5", "preview", "chatgpt"]

EmitterType = Optional[Callable[[dict], Awaitable[None]]]


class SendCitationType(Protocol):
    def __call__(self, url: str, title: str, content: str) -> Awaitable[None]: ...


class SendStatusType(Protocol):
    def __call__(self, status_message: str, done: bool) -> Awaitable[None]: ...


def get_send_citation(__event_emitter__: EmitterType) -> SendCitationType:
    async def send_citation(url: str, title: str, content: str):
        if __event_emitter__ is None:
            return
        await __event_emitter__(
            {
                "type": "citation",
                "data": {
                    "document": [content],
                    "metadata": [{"source": url, "html": False}],
                    "source": {"name": title},
                },
            }
        )

    return send_citation


def get_send_status(__event_emitter__: EmitterType) -> SendStatusType:
    async def send_status(status_message: str, done: bool):
        if __event_emitter__ is None:
            return
        await __event_emitter__(
            {
                "type": "status",
                "data": {"description": status_message, "done": done},
            }
        )

    return send_status


class Pipe:
    class Valves(BaseModel):
        OPENAI_BASE_URL: str = Field(
            default="https://api.openai.com/v1",
            description="Base URL for OpenAI API endpoints",
        )
        OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
        OLLAMA_URL: str = Field(
            default="", description="Base URL for Ollama API endpoints"
        )
        LANGFUSE_SECRET_KEY: str = Field(default="", description="Langfuse secret key")
        LANGFUSE_PUBLIC_KEY: str = Field(default="", description="Langfuse public key")
        LANGFUSE_URL: str = Field(default="", description="Langfuse URL")
        MODEL_PREFIX: str = Field(default="ReAct", description="Prefix before model ID")

    def __init__(self):
        self.type = "manifold"
        self.valves = self.Valves(
            **{k: os.getenv(k, v.default) for k, v in self.Valves.model_fields.items()}
        )
        print(f"{self.valves=}")

    def pipes(self) -> list[dict[str, str]]:
        try:
            self.setup()
        except Exception as e:
            return [{"id": "error", "name": f"Error: {e}"}]
        models = []
        self.model_sources = {}
        if self.openai_kwargs:
            try:
                openai = OpenAI(**self.openai_kwargs)  # type: ignore
                oai_models = [m.id for m in openai.models.list().data if "gpt" in m.id]
                oai_models = [
                    m for m in oai_models if not any(bad in m for bad in BAD_NAMES)
                ]
                models.extend(oai_models)
                self.model_sources |= {m: "openai" for m in oai_models}
            except Exception as e:
                print(f"OpenAI error: {e}")
        if self.ollama_kwargs:
            try:
                ollama_models = [m["name"] for m in ollama.list()["models"]]
                models.extend(ollama_models)
                self.model_sources |= {m: "ollama" for m in ollama_models}
            except Exception as e:
                print(f"Ollama error: {e}")
        return [{"id": m, "name": f"{self.valves.MODEL_PREFIX}/{m}"} for m in models]

    def setup(self):
        v = self.valves
        if v.OPENAI_API_KEY and v.OPENAI_BASE_URL:
            self.openai_kwargs = {
                "base_url": v.OPENAI_BASE_URL,
                "api_key": v.OPENAI_API_KEY,
            }
        else:
            self.openai_kwargs = None
        if v.OLLAMA_URL:
            self.ollama_kwargs = {"base_url": v.OLLAMA_URL}
        else:
            self.ollama_kwargs = None
        if not (self.openai_kwargs or self.ollama_kwargs):
            raise ValueError("No API keys provided")

        lf = (v.LANGFUSE_SECRET_KEY, v.LANGFUSE_PUBLIC_KEY, v.LANGFUSE_URL)
        if not all(lf):
            self.langfuse_kwargs = None
        else:
            self.langfuse_kwargs = {
                "secret_key": v.LANGFUSE_SECRET_KEY,
                "public_key": v.LANGFUSE_PUBLIC_KEY,
                "host": v.LANGFUSE_URL,
            }

    async def pipe(
        self,
        body: dict,
        __user__: dict | None,
        __task__: str | None,
        __tools__: dict[str, dict] | None,
        __event_emitter__: Callable[[dict], Awaitable[None]] | None,
    ) -> AsyncGenerator:
        print(f"{body = }")
        print(__task__)
        print(f"{__tools__=}")
        if __task__ == "function_calling":
            return

        self.setup()
        model_id = ".".join(body["model"].split(".")[1:])
        if self.model_sources[model_id] == "openai":
            assert self.openai_kwargs, "OpenAI API"
            model = ChatOpenAI(model=model_id, **self.openai_kwargs)  # type: ignore
        else:
            assert self.ollama_kwargs, "Ollama API"
            model = ChatOllama(model=model_id, **self.ollama_kwargs)  # type: ignore
        if self.langfuse_kwargs:
            user_kwargs = {"user_id": __user__["id"]} if __user__ else {}
            callback_kwargs = self.langfuse_kwargs | user_kwargs
            callbacks = [CallbackHandler(**callback_kwargs)]  # type: ignore
        else:
            callbacks = []
        config = {"callbacks": callbacks}  # type: ignore

        if __task__ == "title_generation":
            content = model.invoke(body["messages"], config=config).content
            assert isinstance(content, str)
            yield content
            return

        if not __tools__:
            async for chunk in model.astream(body["messages"], config=config):
                content = chunk.content
                assert isinstance(content, str)
                yield content
            return

        send_citation = get_send_citation(__event_emitter__)
        send_status = get_send_status(__event_emitter__)

        tools = []
        for key, value in __tools__.items():
            tools.append(
                StructuredTool(
                    func=None,
                    name=key,
                    coroutine=value["callable"],
                    args_schema=value["pydantic_model"],
                    description=value["spec"]["description"],
                )
            )
        graph = create_react_agent(model, tools=tools)
        inputs = {"messages": body["messages"]}
        num_tool_calls = 0
        async for event in graph.astream_events(inputs, version="v2", config=config):  # type: ignore
            kind = event["event"]
            data = event["data"]
            if kind == "on_chat_model_stream":
                if "chunk" in data and (content := data["chunk"].content):
                    yield content
            elif kind == "on_tool_start":
                yield "\n"
                await send_status(f"Running tool {event['name']}", False)
            elif kind == "on_tool_end":
                num_tool_calls += 1
                await send_status(
                    f"Tool '{event['name']}' returned {data.get('output')}", True
                )
                await send_citation(
                    url=f"Tool call {num_tool_calls}",
                    title=event["name"],
                    content=f"Tool '{event['name']}' with inputs {data.get('input')} returned {data.get('output')}",
                )
