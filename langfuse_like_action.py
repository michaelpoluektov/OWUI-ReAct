"""
icon_url: data:image/svg+xml,%3Csvg%20stroke%3D%22currentColor%22%20fill%3D%22none%22%20stroke-width%3D%222.3%22%20viewBox%3D%220%200%2024%2024%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%20class%3D%22w-4%20h-4%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cpath%20d%3D%22M14%209V5a3%203%200%200%200-3-3l-4%209v11h11.28a2%202%200%200%200%202-1.7l1.38-9a2%202%200%200%200-2-2.3zM7%2022H4a2%202%200%200%201-2-2v-7a2%202%200%200%201%202-2h3%22%3E%3C%2Fpath%3E%3C%2Fsvg%3E
"""

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
        message_id = body.get("id", None)
        langfuse.score(trace_id=message_id, name="reaction", value=1)
        print(f"Liked message {message_id}")
