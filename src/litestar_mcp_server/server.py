"""The server: JSON-RPC in, JSON-RPC out. No HTTP framework in here.

``McpServer.handle`` takes the request body and headers and the caller's context, and returns a
status and a body. The Litestar route in ``plugin.py`` is a thin shell around it.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import msgspec

from litestar_mcp_server.protocol import (
    INVALID_PARAMS,
    LATEST_PROTOCOL_VERSION,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    SUPPORTED_PROTOCOL_VERSIONS,
    Empty,
    InitializeParams,
    InitializeResult,
    JsonRpcRequest,
    ServerInfo,
    TextContent,
    ToolCallParams,
    ToolCallResult,
    ToolsListResult,
    block_size,
    error_response,
    result_response,
    text_result,
)
from litestar_mcp_server.tools import Arguments, Blocks, JsonValue, Tool, ToolError

logger = logging.getLogger("litestar_mcp_server")

_UNEXPECTED = "the tool failed unexpectedly. Try again; if it keeps failing, tell the user it is a server error."


@dataclass(frozen=True, slots=True)
class McpConfig:
    """Identity and limits of one MCP server."""

    name: str
    version: str
    instructions: str = ""
    # The directory rejects servers that dump whole databases. A result over this size is refused
    # with a message telling the agent to narrow the request.
    max_result_bytes: int = 256 * 1024


@dataclass(frozen=True, slots=True)
class McpResponse:
    status: int
    body: bytes
    media_type: str = "application/json"


def _decode_arguments(raw: msgspec.Raw) -> Arguments:
    data = bytes(raw)
    if not data:
        return Arguments(values={})
    decoded: JsonValue = msgspec.json.decode(data)
    if not isinstance(decoded, dict):
        raise ToolError("arguments must be a JSON object")
    return Arguments(values=decoded)


@dataclass(frozen=True, slots=True)
class McpServer[Ctx]:
    """A set of tools behind one MCP endpoint.

    ``Ctx`` is the type the host builds per request (the caller plus whatever the tools need).
    """

    config: McpConfig
    tools: Sequence[Tool[Ctx]]

    def __post_init__(self) -> None:
        names = [t.name for t in self.tools]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"duplicate tool names: {duplicates}")

    # -- listing --------------------------------------------------------------------------------

    def visible_tools(self, ctx: Ctx) -> tuple[Tool[Ctx], ...]:
        """The tools this caller may see.

        A tool whose scope the token lacks is still listed, so the agent can explain what is
        missing; calling it answers with an error that names the scope.
        """
        return tuple(t for t in self.tools if t.is_visible(ctx))

    # -- the entry point ------------------------------------------------------------------------

    async def handle(
        self,
        *,
        body: bytes,
        headers: Mapping[str, str],
        ctx: Ctx,
        scopes: frozenset[str] | None = None,
    ) -> McpResponse:
        """Answer one POST.

        ``scopes`` are the token's scopes, or ``None`` when scopes are not used (then no tool is
        refused for scope).
        """
        version = headers.get("mcp-protocol-version")
        if version is not None and version not in SUPPORTED_PROTOCOL_VERSIONS:
            return McpResponse(
                400,
                error_response(None, INVALID_PARAMS, f"unsupported protocol version {version!r}"),
            )
        try:
            frame = msgspec.json.decode(body, type=JsonRpcRequest)
        except msgspec.DecodeError as exc:
            return McpResponse(200, error_response(None, PARSE_ERROR, f"malformed frame: {exc}"))

        # A notification has no id and gets no body.
        if frame.is_notification:
            return McpResponse(202, b"")

        return await self._dispatch(frame, ctx, scopes)

    async def _dispatch(
        self, frame: JsonRpcRequest, ctx: Ctx, scopes: frozenset[str] | None
    ) -> McpResponse:
        match frame.method:
            case "initialize":
                return self._initialize(frame)
            case "ping":
                return McpResponse(200, result_response(frame.id, Empty()))
            case "tools/list":
                listing = ToolsListResult(
                    tools=tuple(t.descriptor() for t in self.visible_tools(ctx))
                )
                return McpResponse(200, result_response(frame.id, listing))
            case "tools/call":
                return await self._tools_call(frame, ctx, scopes)
            case other:
                return McpResponse(
                    200,
                    error_response(
                        frame.id, METHOD_NOT_FOUND, f"method {other!r} is not supported"
                    ),
                )

    def _initialize(self, frame: JsonRpcRequest) -> McpResponse:
        try:
            params = msgspec.json.decode(bytes(frame.params) or b"{}", type=InitializeParams)
        except msgspec.DecodeError as exc:
            return McpResponse(200, error_response(frame.id, INVALID_PARAMS, f"bad params: {exc}"))
        # Echo the client's version when we support it, otherwise offer our latest (spec).
        chosen = (
            params.protocol_version
            if params.protocol_version in SUPPORTED_PROTOCOL_VERSIONS
            else LATEST_PROTOCOL_VERSION
        )
        result = InitializeResult(
            protocol_version=chosen,
            server_info=ServerInfo(name=self.config.name, version=self.config.version),
            instructions=self.config.instructions,
        )
        return McpResponse(200, result_response(frame.id, result))

    async def _tools_call(
        self, frame: JsonRpcRequest, ctx: Ctx, scopes: frozenset[str] | None
    ) -> McpResponse:
        try:
            params = msgspec.json.decode(bytes(frame.params) or b"{}", type=ToolCallParams)
        except msgspec.DecodeError as exc:
            return McpResponse(200, error_response(frame.id, INVALID_PARAMS, f"bad params: {exc}"))
        result = await self.call_tool(ctx, params.name, params.arguments, scopes)
        return McpResponse(200, result_response(frame.id, result))

    def _refusal(self, tool: Tool[Ctx] | None, name: str, scopes: frozenset[str] | None) -> str:
        """Why this call must not run, or an empty string when it may."""
        if tool is None:
            # Also the answer for a tool the caller may not see: its existence is not revealed.
            return f"unknown tool {name!r}; call tools/list to see the tools"
        if tool.scope and scopes is not None and tool.scope not in scopes:
            return (
                f"this connection lacks the {tool.scope!r} permission needed for {tool.name}. "
                "Tell the user to reconnect and allow it."
            )
        return ""

    async def call_tool(
        self, ctx: Ctx, name: str, raw_arguments: msgspec.Raw, scopes: frozenset[str] | None
    ) -> ToolCallResult:
        tool = next((t for t in self.tools if t.name == name and t.is_visible(ctx)), None)
        refusal = self._refusal(tool, name, scopes)
        if tool is None or refusal:
            return text_result(refusal, is_error=True)
        try:
            arguments = _decode_arguments(raw_arguments)
            output = await tool.handler(ctx, arguments)
        except (ToolError, ValueError) as exc:
            return text_result(str(exc), is_error=True)
        except Exception:
            logger.exception("tool %s failed", tool.name)
            return text_result(_UNEXPECTED, is_error=True)
        if isinstance(output, Blocks):
            content = output.items
            size = sum(block_size(b) for b in content)
        else:
            text = output if isinstance(output, str) else msgspec.json.encode(output).decode()
            content = (TextContent(text=text),)
            size = len(text.encode())
        if size > self.config.max_result_bytes:
            return text_result(
                f"the result of {tool.name} is too large to return. "
                "Ask for fewer items, a shorter time range or a narrower filter.",
                is_error=True,
            )
        return ToolCallResult(content=content)
