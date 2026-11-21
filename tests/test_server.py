import json
from typing import Any

import pytest

from litestar_mcp_server import (
    Arguments,
    AudioContent,
    BlobResource,
    Blocks,
    Effect,
    EmbeddedResource,
    ImageContent,
    McpConfig,
    McpServer,
    TextContent,
    Tool,
    object_schema,
)
from tests.conftest import Ctx

ALICE = Ctx(user="alice")
OPERATOR = Ctx(user="root", operator=True)


def frame(method: str, params: dict[str, object] | None = None, id_: int | None = 1) -> bytes:
    body: dict[str, object] = {"jsonrpc": "2.0", "method": method}
    if id_ is not None:
        body["id"] = id_
    if params is not None:
        body["params"] = params
    return json.dumps(body).encode()


async def call(
    server: McpServer[Ctx],
    method: str,
    params: dict[str, object] | None = None,
    *,
    ctx: Ctx = ALICE,
    scopes: frozenset[str] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any]:
    answer = await server.handle(
        body=frame(method, params), headers=headers or {}, ctx=ctx, scopes=scopes
    )
    return answer.status, json.loads(answer.body) if answer.body else {}


@pytest.mark.anyio
async def test_initialize_echoes_a_supported_version(server: McpServer[Ctx]) -> None:
    status, body = await call(server, "initialize", {"protocolVersion": "2025-06-18"})
    result = body["result"]
    assert status == 200
    assert result["protocolVersion"] == "2025-06-18"
    assert result["serverInfo"] == {"name": "things", "version": "1.2.3"}
    assert result["instructions"] == "Use the tools."


@pytest.mark.anyio
async def test_initialize_offers_the_latest_for_an_unknown_version(server: McpServer[Ctx]) -> None:
    _, body = await call(server, "initialize", {"protocolVersion": "1999-01-01"})
    result = body["result"]
    assert result["protocolVersion"] == "2025-11-25"


@pytest.mark.anyio
async def test_unsupported_protocol_header_is_http_400(server: McpServer[Ctx]) -> None:
    status, _ = await call(server, "ping", headers={"mcp-protocol-version": "1999-01-01"})
    assert status == 400


@pytest.mark.anyio
async def test_notification_gets_202_and_no_body(server: McpServer[Ctx]) -> None:
    answer = await server.handle(
        body=frame("notifications/initialized", id_=None), headers={}, ctx=ALICE
    )
    assert (answer.status, answer.body) == (202, b"")


@pytest.mark.anyio
async def test_malformed_frame_is_a_parse_error(server: McpServer[Ctx]) -> None:
    answer = await server.handle(body=b"{not json", headers={}, ctx=ALICE)
    assert json.loads(answer.body)["error"]["code"] == -32700


@pytest.mark.anyio
async def test_unknown_method(server: McpServer[Ctx]) -> None:
    _, body = await call(server, "resources/list")
    error = body["error"]
    assert error["code"] == -32601


@pytest.mark.anyio
async def test_ping(server: McpServer[Ctx]) -> None:
    _, body = await call(server, "ping")
    assert body["result"] == {}


@pytest.mark.anyio
async def test_list_has_title_and_hints_on_every_tool(server: McpServer[Ctx]) -> None:
    _, body = await call(server, "tools/list")
    result = body["result"]
    tools = {t["name"]: t for t in result["tools"]}
    assert tools["list_things"]["title"] == "List things"
    assert tools["list_things"]["annotations"] == {"title": "List things", "readOnlyHint": True}
    assert tools["create_thing"]["annotations"] == {
        "title": "Create a thing",
        "readOnlyHint": False,
        "destructiveHint": False,
    }
    for tool in tools.values():
        assert tool["title"]
        assert tool["inputSchema"]["type"] == "object"


@pytest.mark.anyio
async def test_operator_tools_are_hidden_from_others(server: McpServer[Ctx]) -> None:
    _, as_alice = await call(server, "tools/list", ctx=ALICE)
    _, as_root = await call(server, "tools/list", ctx=OPERATOR)
    names_alice = {t["name"] for t in as_alice["result"]["tools"]}
    names_root = {t["name"] for t in as_root["result"]["tools"]}
    assert "triage" not in names_alice
    assert "triage" in names_root


@pytest.mark.anyio
async def test_hidden_tool_answers_as_unknown(server: McpServer[Ctx]) -> None:
    _, body = await call(server, "tools/call", {"name": "triage", "arguments": {}}, ctx=ALICE)
    result = body["result"]
    assert result["isError"] is True
    assert "unknown tool" in result["content"][0]["text"]


@pytest.mark.anyio
async def test_call_returns_encoded_output(server: McpServer[Ctx]) -> None:
    _, body = await call(server, "tools/call", {"name": "list_things", "arguments": {"limit": 3}})
    result = body["result"]
    assert result["isError"] is False
    assert json.loads(result["content"][0]["text"]) == {"owner": "alice", "limit": 3}


@pytest.mark.anyio
async def test_call_with_string_output(server: McpServer[Ctx]) -> None:
    _, body = await call(server, "tools/call", {"name": "create_thing", "arguments": {"name": "n"}})
    assert body["result"]["content"][0]["text"] == "created n for alice"


@pytest.mark.anyio
async def test_missing_argument_is_a_readable_error(server: McpServer[Ctx]) -> None:
    _, body = await call(server, "tools/call", {"name": "create_thing", "arguments": {}})
    result = body["result"]
    assert result["isError"] is True
    assert "'name'" in result["content"][0]["text"]


@pytest.mark.anyio
async def test_tool_error_message_reaches_the_agent(server: McpServer[Ctx]) -> None:
    _, body = await call(server, "tools/call", {"name": "fail", "arguments": {}})
    assert body["result"]["content"][0]["text"] == "thing not found; call list_things first"


@pytest.mark.anyio
async def test_unexpected_exception_does_not_leak_details(server: McpServer[Ctx]) -> None:
    _, body = await call(server, "tools/call", {"name": "boom", "arguments": {}})
    result = body["result"]
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert "secret internal detail" not in text
    assert "failed unexpectedly" in text


@pytest.mark.anyio
async def test_oversized_result_is_refused_with_advice(server: McpServer[Ctx]) -> None:
    _, body = await call(server, "tools/call", {"name": "big", "arguments": {}})
    result = body["result"]
    assert result["isError"] is True
    assert "too large" in result["content"][0]["text"]


@pytest.mark.anyio
async def test_scope_is_enforced_per_tool(server: McpServer[Ctx]) -> None:
    read_only = frozenset({"things:read"})
    _, ok = await call(
        server, "tools/call", {"name": "list_things", "arguments": {}}, scopes=read_only
    )
    _, denied = await call(
        server, "tools/call", {"name": "create_thing", "arguments": {"name": "n"}}, scopes=read_only
    )
    assert ok["result"]["isError"] is False
    assert denied["result"]["isError"] is True
    assert "things:write" in denied["result"]["content"][0]["text"]


@pytest.mark.anyio
async def test_scopes_are_not_checked_when_not_used(server: McpServer[Ctx]) -> None:
    _, body = await call(
        server, "tools/call", {"name": "create_thing", "arguments": {"name": "n"}}, scopes=None
    )
    assert body["result"]["isError"] is False


def test_a_title_over_64_characters_is_refused() -> None:
    from litestar_mcp_server import Effect, object_schema

    async def handler(ctx: Ctx, args: object) -> str:
        return ""

    with pytest.raises(ValueError, match="title"):
        Tool(
            name="t",
            title="x" * 65,
            effect=Effect.READ,
            description="d",
            input_schema=object_schema(),
            handler=handler,
        )


def test_duplicate_tool_names_are_refused(server: McpServer[Ctx]) -> None:
    from litestar_mcp_server import McpConfig

    with pytest.raises(ValueError, match="duplicate"):
        McpServer(config=McpConfig(name="n", version="1"), tools=[*server.tools, server.tools[0]])


def test_required_must_be_declared() -> None:
    from litestar_mcp_server import object_schema

    with pytest.raises(ValueError, match="not declared"):
        object_schema({}, required=("x",))


async def _plot(ctx: Ctx, args: Arguments) -> Blocks:
    return Blocks(
        (TextContent(text="a plot"), ImageContent(data="iVBORw0KGgo=", mime_type="image/png"))
    )


def _plot_server(max_result_bytes: int) -> McpServer[Ctx]:
    tool = Tool(
        name="plot",
        title="Get a plot",
        effect=Effect.READ,
        description="A text block and a picture.",
        input_schema=object_schema(),
        handler=_plot,
    )
    config = McpConfig(name="t", version="1", max_result_bytes=max_result_bytes)
    return McpServer(config=config, tools=[tool])


@pytest.mark.anyio
async def test_blocks_are_sent_as_text_and_image_content() -> None:
    _, body = await call(_plot_server(1000), "tools/call", {"name": "plot", "arguments": {}})
    result = body["result"]
    assert result["isError"] is False
    assert result["content"] == [
        {"text": "a plot", "type": "text"},
        {"data": "iVBORw0KGgo=", "mimeType": "image/png", "type": "image"},
    ]


@pytest.mark.anyio
async def test_the_size_cap_counts_image_data() -> None:
    _, body = await call(_plot_server(10), "tools/call", {"name": "plot", "arguments": {}})
    result = body["result"]
    assert result["isError"] is True
    assert "too large" in result["content"][0]["text"]


async def _files(ctx: Ctx, args: Arguments) -> Blocks:
    return Blocks(
        (
            AudioContent(data="UklGRg==", mime_type="audio/wav"),
            EmbeddedResource(
                BlobResource(uri="file:///report.pdf", blob="JVBERi0=", mime_type="application/pdf")
            ),
        )
    )


def _files_server(max_result_bytes: int) -> McpServer[Ctx]:
    tool = Tool(
        name="files",
        title="Get a sound and a file",
        effect=Effect.READ,
        description="An audio block and a PDF.",
        input_schema=object_schema(),
        handler=_files,
    )
    config = McpConfig(name="t", version="1", max_result_bytes=max_result_bytes)
    return McpServer(config=config, tools=[tool])


@pytest.mark.anyio
async def test_audio_and_embedded_resource_follow_the_spec_shape() -> None:
    _, body = await call(_files_server(1000), "tools/call", {"name": "files", "arguments": {}})
    result = body["result"]
    assert result["isError"] is False
    assert result["content"] == [
        {"data": "UklGRg==", "mimeType": "audio/wav", "type": "audio"},
        {
            "resource": {
                "blob": "JVBERi0=",
                "mimeType": "application/pdf",
                "uri": "file:///report.pdf",
            },
            "type": "resource",
        },
    ]


@pytest.mark.anyio
async def test_the_size_cap_counts_audio_and_blob_data() -> None:
    # 8 bytes of audio + 8 bytes of blob = 16: a cap of 15 refuses, a cap of 16 allows.
    _, refused = await call(_files_server(15), "tools/call", {"name": "files", "arguments": {}})
    _, allowed = await call(_files_server(16), "tools/call", {"name": "files", "arguments": {}})
    assert refused["result"]["isError"] is True
    assert allowed["result"]["isError"] is False
