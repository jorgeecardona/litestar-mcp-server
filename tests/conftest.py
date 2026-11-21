from dataclasses import dataclass

import pytest

from litestar_mcp_server import (
    Arguments,
    Effect,
    McpConfig,
    McpServer,
    Tool,
    ToolError,
    boolean,
    integer,
    object_schema,
    string,
)


@dataclass(frozen=True, slots=True)
class Ctx:
    """The per-request context a host builds: who is calling."""

    user: str
    operator: bool = False


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _list_things(ctx: Ctx, args: Arguments) -> dict[str, str | int]:
    return {"owner": ctx.user, "limit": args.optional_integer("limit", default=10)}


async def _create_thing(ctx: Ctx, args: Arguments) -> str:
    return f"created {args.string('name')} for {ctx.user}"


async def _fail(ctx: Ctx, args: Arguments) -> str:
    raise ToolError("thing not found; call list_things first")


async def _boom(ctx: Ctx, args: Arguments) -> str:
    raise RuntimeError("secret internal detail")


async def _big(ctx: Ctx, args: Arguments) -> str:
    return "x" * 2000


async def _triage(ctx: Ctx, args: Arguments) -> str:
    return "triaged"


def make_tools() -> list[Tool[Ctx]]:
    return [
        Tool(
            name="list_things",
            title="List things",
            effect=Effect.READ,
            description="List the things of the caller.",
            input_schema=object_schema({"limit": integer("max items", minimum=1)}),
            handler=_list_things,
            scope="things:read",
        ),
        Tool(
            name="create_thing",
            title="Create a thing",
            effect=Effect.ADDITIVE,
            description="Create a thing.",
            input_schema=object_schema({"name": string("the name")}, required=("name",)),
            handler=_create_thing,
            scope="things:write",
        ),
        Tool(
            name="fail",
            title="Always fails with a message",
            effect=Effect.READ,
            description="x",
            input_schema=object_schema(),
            handler=_fail,
        ),
        Tool(
            name="boom",
            title="Raises an unexpected error",
            effect=Effect.READ,
            description="x",
            input_schema=object_schema({"flag": boolean("a flag")}),
            handler=_boom,
        ),
        Tool(
            name="big",
            title="Returns too much",
            effect=Effect.READ,
            description="x",
            input_schema=object_schema(),
            handler=_big,
        ),
        Tool(
            name="triage",
            title="Operator only",
            effect=Effect.DESTRUCTIVE,
            description="x",
            input_schema=object_schema(),
            handler=_triage,
            visible=lambda ctx: ctx.operator,
        ),
    ]


@pytest.fixture
def server() -> McpServer[Ctx]:
    return McpServer(
        config=McpConfig(
            name="things", version="1.2.3", instructions="Use the tools.", max_result_bytes=1000
        ),
        tools=make_tools(),
    )
