import json
import subprocess
import sys
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from litestar_mcp_server import Effect, McpConfig, McpServer
from litestar_mcp_server.pydantic import model_tool
from tests.conftest import Ctx
from tests.test_server import ALICE, call


class Search(BaseModel):
    """Search the things."""

    query: str = Field(min_length=1, description="what to find")
    limit: int = Field(10, ge=1, le=100, description="max items")
    mode: Literal["fast", "slow"] = "fast"


async def _search(ctx: Ctx, args: Search) -> dict[str, str | int]:
    return {"owner": ctx.user, "query": args.query, "limit": args.limit, "mode": args.mode}


def _server() -> McpServer[Ctx]:
    tool = model_tool(
        name="search",
        title="Search things",
        effect=Effect.READ,
        description="Search the things of the caller.",
        model=Search,
        handler=_search,
        scope="things:read",
    )
    return McpServer(config=McpConfig(name="t", version="1"), tools=[tool])


@pytest.mark.anyio
async def test_the_model_gives_the_input_schema() -> None:
    _, body = await call(_server(), "tools/list")
    tool = body["result"]["tools"][0]
    schema = tool["inputSchema"]
    assert schema["type"] == "object"
    assert schema["required"] == ["query"]
    assert schema["properties"]["query"]["description"] == "what to find"
    assert schema["properties"]["limit"]["maximum"] == 100
    assert schema["properties"]["mode"]["enum"] == ["fast", "slow"]
    assert tool["annotations"] == {"title": "Search things", "readOnlyHint": True}


@pytest.mark.anyio
async def test_the_handler_gets_the_validated_model() -> None:
    arguments = {"query": "cats", "limit": 5}
    _, body = await call(_server(), "tools/call", {"name": "search", "arguments": arguments})
    result = body["result"]
    assert result["isError"] is False
    expected = {"owner": "alice", "query": "cats", "limit": 5, "mode": "fast"}
    assert json.loads(result["content"][0]["text"]) == expected


@pytest.mark.anyio
async def test_wrong_arguments_name_each_field_and_hide_the_value() -> None:
    arguments = {"query": "", "limit": 1000, "mode": "secret-value"}
    _, body = await call(_server(), "tools/call", {"name": "search", "arguments": arguments})
    result = body["result"]
    text = result["content"][0]["text"]
    assert result["isError"] is True
    assert text.startswith("invalid arguments: ")
    assert "query: String should have at least 1 character" in text
    assert "limit: Input should be less than or equal to 100" in text
    assert "mode: " in text
    assert "secret-value" not in text


@pytest.mark.anyio
async def test_a_missing_argument_is_a_readable_error() -> None:
    _, body = await call(_server(), "tools/call", {"name": "search", "arguments": {}})
    result = body["result"]
    assert result["isError"] is True
    assert "query: Field required" in result["content"][0]["text"]


@pytest.mark.anyio
async def test_scope_and_visibility_still_apply() -> None:
    arguments = {"query": "cats"}
    _, denied = await call(
        _server(),
        "tools/call",
        {"name": "search", "arguments": arguments},
        ctx=ALICE,
        scopes=frozenset({"other"}),
    )
    assert denied["result"]["isError"] is True
    assert "things:read" in denied["result"]["content"][0]["text"]


def test_the_base_package_does_not_import_pydantic() -> None:
    code = (
        "import sys; sys.modules['pydantic'] = None; "
        "import litestar_mcp_server; print(litestar_mcp_server.__version__)"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)  # noqa: S603
    assert done.returncode == 0, done.stderr
