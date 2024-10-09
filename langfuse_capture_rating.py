"""
title: Langfuse Ratings Action
author: Michael Poluektov
author_url: https://github.com/michaelpoluektov
git_url: https://github.com/michaelpoluektov/OWUI-ReAct
description: Capture like/dislike events and send them to Langfuse
required_open_webui_version: 0.3.15
version: 0.1.0
licence: MIT
"""

# In order for this to work, you need to make sure the observation ID if you trace
# is set to the OWUI message ID. In LangChain, this is done by passing the `run_id` argument
# in the config of invoke. Check the git repo for an example.

import os
from typing import Optional
from pydantic import BaseModel, Field
from langfuse import Langfuse


class Action:
    class Valves(BaseModel):
        LANGFUSE_SECRET_KEY: str = Field(default="", description="Langfuse secret key")
        LANGFUSE_PUBLIC_KEY: str = Field(default="", description="Langfuse public key")
        LANGFUSE_URL: str = Field(default="", description="Langfuse URL")

        def valid(self) -> bool:
            return all(self.__dict__.values())

    def __init__(self):
        self.__webui__ = True
        self.valves = self.Valves(
            **{k: os.getenv(k, v.default) for k, v in self.Valves.model_fields.items()}
        )

    async def action(
        self,
        body: dict,
        __id__=None,
        __user__=None,
        __event_emitter__=None,
        __event_call__=None,
    ) -> Optional[dict]:
        v = self.valves
        if not v.valid():
            print("Langfuse valves not configured properly, ignoring...")
            return
        langfuse = Langfuse(
            host=v.LANGFUSE_URL,
            public_key=v.LANGFUSE_PUBLIC_KEY,
            secret_key=v.LANGFUSE_SECRET_KEY,
        )
        # Only trigger on like/dislike events
        event = body.get("event", {})
        event_id = event.get("id", "")
        if event_id in ["good-response", "bad-response"]:
            message_id = event.get("data", {}).get("messageId")
            score = int(event_id == "good-response")
            langfuse.score(trace_id=message_id, name="reaction", value=score)
            print(f"Message ID: {message_id}, {score = }")
