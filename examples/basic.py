"""A Litestar API with one MCP endpoint and two tools.

Run it with:  uv run litestar --app examples.basic:app run

Authentication is a placeholder guard here. In a real app use ``bearer_guard`` from
``litestar-oauth-server`` and read the token's scopes with ``verified_token``.
"""

from dataclasses import dataclass
from typing import Any

from litestar import Litestar, Request
from litestar.di import Provide

from litestar_mcp_server import (
    Arguments,
    Effect,
    McpConfig,
    McpServer,
    Tool,
    mcp_handlers,
    object_schema,
    string,
)


@dataclass(frozen=True, slots=True)
class Ctx:
    """What the tools need about the caller. Build it from your own session or token."""

    user: str


async def list_notes(ctx: Ctx, args: Arguments) -> list[str]:
    return [f"note of {ctx.user}"]


async def add_note(ctx: Ctx, args: Arguments) -> str:
    return f"added {args.string('text')!r} for {ctx.user}"


server = McpServer(
    config=McpConfig(name="notes", version="0.1.0", instructions="Read and add the user's notes."),
    tools=[
        Tool(
            name="list_notes",
            title="List my notes",
            effect=Effect.READ,
            description="List the notes of the signed-in user.",
            input_schema=object_schema(),
            handler=list_notes,
        ),
        Tool(
            name="add_note",
            title="Add a note",
            effect=Effect.ADDITIVE,
            description="Add a note for the signed-in user.",
            input_schema=object_schema({"text": string("the note")}, required=("text",)),
            handler=add_note,
            scope="notes:write",
        ),
    ],
)


async def build_ctx(request: Request[Any, Any, Any]) -> Ctx:
    return Ctx(user="demo")


app = Litestar(
    mcp_handlers(server, path="/mcp", dependencies={"mcp_context": Provide(build_ctx)}),
)
