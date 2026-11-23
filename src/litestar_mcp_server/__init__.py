"""A small MCP server for Litestar, with no SDK."""

from litestar_mcp_server.plugin import mcp_handlers
from litestar_mcp_server.protocol import (
    LATEST_PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    AudioContent,
    BlobResource,
    EmbeddedResource,
    ImageContent,
    TextContent,
)
from litestar_mcp_server.server import McpConfig, McpResponse, McpServer
from litestar_mcp_server.tools import (
    TITLE_MAX,
    Arguments,
    Blocks,
    Effect,
    JsonObject,
    JsonValue,
    Tool,
    ToolError,
    boolean,
    integer,
    object_schema,
    string,
)

__version__ = "0.0.5"  # the single source of truth; pyproject reads it via [tool.hatch.version]

__all__ = [
    "LATEST_PROTOCOL_VERSION",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "TITLE_MAX",
    "Arguments",
    "AudioContent",
    "BlobResource",
    "Blocks",
    "Effect",
    "EmbeddedResource",
    "ImageContent",
    "JsonObject",
    "JsonValue",
    "McpConfig",
    "McpResponse",
    "McpServer",
    "TextContent",
    "Tool",
    "ToolError",
    "__version__",
    "boolean",
    "integer",
    "mcp_handlers",
    "object_schema",
    "string",
]
