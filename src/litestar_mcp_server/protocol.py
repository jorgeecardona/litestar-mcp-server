"""The MCP wire frames: msgspec Structs, no SDK.

This is the stateless, JSON-only subset of Streamable HTTP:

- POST always answers ``application/json`` with ONE JSON object (we never open an SSE stream);
- GET answers 405 (no server-initiated stream);
- no ``Mcp-Session-Id`` is ever issued (sessions are a server MAY);
- an unsupported ``MCP-Protocol-Version`` header answers HTTP 400.

A frame is decoded at the boundary into a Struct, never threaded as a loose dict.
"""

from __future__ import annotations

import msgspec

LATEST_PROTOCOL_VERSION = "2025-11-25"
# 2025-03-26 is what the spec tells a server to assume when the header is absent.
SUPPORTED_PROTOCOL_VERSIONS: tuple[str, ...] = (LATEST_PROTOCOL_VERSION, "2025-06-18", "2025-03-26")

# JSON-RPC error codes this server emits.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class JsonRpcRequest(msgspec.Struct, frozen=True):
    """One incoming frame. ``params`` stays raw; each method decodes it into its own Struct."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str = ""
    # A bare Raw with an empty default, NOT ``Raw | None``: in a union msgspec validates the object
    # against the None arm and rejects it. ``bytes(params)`` is b"" when ``params`` was omitted.
    params: msgspec.Raw = msgspec.Raw(b"")

    @property
    def is_notification(self) -> bool:
        return self.id is None


class InitializeParams(msgspec.Struct, frozen=True, rename="camel"):
    protocol_version: str = ""


class ToolCallParams(msgspec.Struct, frozen=True):
    """``tools/call``. ``arguments`` stays raw bytes; the server wraps them in ``Arguments``."""

    name: str = ""
    arguments: msgspec.Raw = msgspec.Raw(b"")


class ServerInfo(msgspec.Struct, frozen=True, rename="camel"):
    name: str
    version: str


class ToolsCapability(msgspec.Struct, frozen=True, rename="camel"):
    # The visible tool set can vary by caller (operator tools, scopes), so a client that lists
    # again after signing in may see a different set.
    list_changed: bool = True


class ServerCapabilities(msgspec.Struct, frozen=True, rename="camel"):
    tools: ToolsCapability = ToolsCapability()


class InitializeResult(msgspec.Struct, frozen=True, rename="camel"):
    protocol_version: str
    server_info: ServerInfo
    capabilities: ServerCapabilities = ServerCapabilities()
    instructions: str = ""


class ToolAnnotations(msgspec.Struct, frozen=True, rename="camel", omit_defaults=True):
    """The hints a connector directory reads.

    A read tool carries ``readOnlyHint: true`` and nothing else. Every other tool carries
    ``readOnlyHint: false`` and ``destructiveHint`` (true or false). The directory's scan asks
    for ``readOnlyHint`` on every tool, and ``destructiveHint`` only means something when
    ``readOnlyHint`` is false (MCP spec).
    """

    title: str
    read_only_hint: bool | None = None
    destructive_hint: bool | None = None


class ToolDescriptor(msgspec.Struct, frozen=True, rename="camel"):
    """One entry of ``tools/list``.

    ``title`` is sent at the top level and inside ``annotations``, because clients and the
    directory read either.
    """

    name: str
    title: str
    description: str
    input_schema: msgspec.Raw
    annotations: ToolAnnotations


class ToolsListResult(msgspec.Struct, frozen=True, rename="camel"):
    tools: tuple[ToolDescriptor, ...] = ()


class TextContent(msgspec.Struct, frozen=True, rename="camel"):
    text: str
    type: str = "text"


class ImageContent(msgspec.Struct, frozen=True, rename="camel"):
    """A picture for the agent: base64 bytes and their MIME type (``image/png``)."""

    data: str
    mime_type: str
    type: str = "image"


class AudioContent(msgspec.Struct, frozen=True, rename="camel"):
    """A sound for the agent: base64 bytes and their MIME type (``audio/wav``)."""

    data: str
    mime_type: str
    type: str = "audio"


class BlobResource(msgspec.Struct, frozen=True, rename="camel"):
    """Any binary file: a ``uri`` that names it, its base64 bytes and its MIME type."""

    uri: str
    blob: str
    mime_type: str


class EmbeddedResource(msgspec.Struct, frozen=True, rename="camel"):
    """A binary file sent inside the tool result, for types with no block of their own (PDF, zip)."""

    resource: BlobResource
    type: str = "resource"


type ContentBlock = TextContent | ImageContent | AudioContent | EmbeddedResource


def block_size(block: ContentBlock) -> int:
    """Return the bytes a block adds to a result: its text, or its base64 payload."""
    match block:
        case TextContent():
            return len(block.text.encode())
        case ImageContent() | AudioContent():
            return len(block.data.encode())
        case EmbeddedResource():
            return len(block.resource.blob.encode())


class ToolCallResult(msgspec.Struct, frozen=True, rename="camel"):
    """A tool outcome.

    A tool failure is a RESULT with ``is_error`` so the agent can read and react; JSON-RPC errors
    are for protocol breakage only.
    """

    content: tuple[ContentBlock, ...] = ()
    is_error: bool = False


class JsonRpcError(msgspec.Struct, frozen=True):
    code: int
    message: str


class JsonRpcErrorResponse(msgspec.Struct, frozen=True):
    error: JsonRpcError
    id: int | str | None = None
    jsonrpc: str = "2.0"


class JsonRpcResultResponse(msgspec.Struct, frozen=True):
    result: msgspec.Raw
    id: int | str | None = None
    jsonrpc: str = "2.0"


class Empty(msgspec.Struct, frozen=True):
    """The ``{}`` result of ``ping``."""


def result_response(id_: int | str | None, result: msgspec.Struct) -> bytes:
    """Encode a full success envelope: the result first, then embedded raw in the envelope."""
    return msgspec.json.encode(
        JsonRpcResultResponse(id=id_, result=msgspec.Raw(msgspec.json.encode(result)))
    )


def error_response(id_: int | str | None, code: int, message: str) -> bytes:
    return msgspec.json.encode(
        JsonRpcErrorResponse(id=id_, error=JsonRpcError(code=code, message=message))
    )


def text_result(text: str, *, is_error: bool = False) -> ToolCallResult:
    return ToolCallResult(content=(TextContent(text=text),), is_error=is_error)
