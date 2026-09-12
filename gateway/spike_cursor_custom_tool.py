"""Spike: Cursor SDK custom tool via AsyncClient (Windows-safe)."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from cursor_sdk import (
    AgentOptions,
    AsyncAgent,
    AsyncClient,
    CustomTool,
    CustomToolContext,
    LocalAgentOptions,
    SendOptions,
)

KEY = Path.home().joinpath(".cc-bridge/secrets/cursor-api.key").read_text(encoding="utf-8").strip()
os.environ["CURSOR_API_KEY"] = KEY

events: list[str] = []
called = asyncio.Event()


def ping(args, context: CustomToolContext):
    events.append(f"EXECUTE ping args={args} id={context.tool_call_id}")
    called.set()
    return "pong"


async def main() -> None:
    cwd = str(Path(__file__).resolve().parent)
    client = await AsyncClient.launch_bridge(workspace=cwd, timeout=60)
    try:
        agent = await AsyncAgent.create(
            AgentOptions(
                model="composer-2.5",
                api_key=KEY,
                tools=["mcp"],
                local=LocalAgentOptions(
                    cwd=cwd,
                    setting_sources=[],
                    custom_tools={
                        "ping": CustomTool(
                            description="Health check. Call this and return the result.",
                            input_schema={
                                "type": "object",
                                "properties": {
                                    "note": {"type": "string"},
                                },
                            },
                            execute=ping,
                        )
                    },
                ),
            ),
            client=client,
        )
        print("agent", agent)
        print("agent_id", getattr(agent, "id", None) or getattr(agent, "agent_id", None))
        run = await agent.send(
            "Call the ping tool now with note=spike. Then stop. Do not read files.",
            SendOptions(on_delta=lambda u: events.append(f"DELTA {type(u).__name__}")),
        )
        result = await run.wait()
        print("status", getattr(result, "status", None))
        print("text", (getattr(result, "result", None) or "")[:500])
        print("called", called.is_set())
        print("events:")
        for e in events:
            print(" ", e[:240])
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
