"""The agent's tools in sandboxed mode: thin HTTP clients of the executor.

They are built from the executor's /tools listing, so the agent process has no tool body
and no data of its own. If the executor cannot be reached the call raises; there is no
local fallback (the `--no-builtin-tools` idea from the external sandbox pattern).
"""

from __future__ import annotations

import json

import httpx
from langchain_core.tools import BaseTool, StructuredTool

EXECUTOR_URL = "http://127.0.0.1:8787"


def executor_client(base_url: str = EXECUTOR_URL) -> httpx.Client:
    # Quarantine calls run inside the executor, so allow a slow local model.
    return httpx.Client(base_url=base_url, timeout=180)


def build_remote_tools(session_id: str, client: httpx.Client) -> list[BaseTool]:
    specs = client.get("/tools").raise_for_status().json()
    return [_remote_tool(spec, session_id, client) for spec in specs]


def _remote_tool(spec: dict, session_id: str, client: httpx.Client) -> BaseTool:
    def call(**args) -> str:
        response = client.post("/call", json={"session": session_id, "tool": spec["name"],
                                              "args": args})
        return json.dumps(response.raise_for_status().json())

    return StructuredTool.from_function(
        func=call, name=spec["name"], description=spec["description"],
        args_schema=spec["schema"],
    )
