"""Tools: what a tool is, how it reads its arguments, and how its schema is written.

A tool has a ``title`` and an ``effect``. The effect is one value, so a tool cannot be read-only and
destructive at once, and the directory hints come out right by construction:

- ``Effect.READ``: changes nothing, ``readOnlyHint: true``;
- ``Effect.ADDITIVE``: adds or moves data and removes or publishes nothing, ``destructiveHint: false``;
- ``Effect.DESTRUCTIVE``: overwrites, deletes, publishes, runs code or messages someone,
  ``destructiveHint: true``.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import Enum

import msgspec

from litestar_mcp_server.protocol import ContentBlock, ToolAnnotations, ToolDescriptor

# What a JSON document can hold. Used for typing only; values are decoded by ``msgspec.json``.
type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
type JsonObject = dict[str, JsonValue]

TITLE_MAX = 64  # the connector directory's limit
NAME_MAX = 64


class Effect(Enum):
    READ = "read"
    ADDITIVE = "additive"
    DESTRUCTIVE = "destructive"


class ToolError(Exception):
    """A failure the agent should see and act on.

    The message is shown to the model, so say what went wrong and what to do next ("notebook not
    found; call list_notebooks").
    """


@dataclass(frozen=True, slots=True)
class Arguments:
    """The arguments of a ``tools/call``, with typed getters.

    Every getter raises ``ToolError`` with a message naming the argument. Build it from the decoded
    JSON object.
    """

    values: Mapping[str, JsonValue]

    def has(self, key: str) -> bool:
        return self.values.get(key) is not None

    def text(self, key: str) -> str:
        """A required string. May be empty (a cell's source can be empty)."""
        raw = self.values.get(key)
        if not isinstance(raw, str):
            raise ToolError(f"missing required argument {key!r} (a string)")
        return raw

    def string(self, key: str) -> str:
        """A required, non-empty string."""
        raw = self.text(key)
        if not raw:
            raise ToolError(f"argument {key!r} must not be empty")
        return raw

    def optional_string(self, key: str) -> str | None:
        raw = self.values.get(key)
        if raw is None or raw == "":
            return None
        if not isinstance(raw, str):
            raise ToolError(f"argument {key!r} must be a string")
        return raw

    def integer(self, key: str) -> int:
        raw = self.values.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ToolError(f"missing required argument {key!r} (an integer)")
        return raw

    def optional_integer(self, key: str, *, default: int) -> int:
        raw = self.values.get(key)
        if raw is None:
            return default
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ToolError(f"argument {key!r} must be an integer")
        return raw

    def boolean(self, key: str, *, default: bool = False) -> bool:
        raw = self.values.get(key)
        if raw is None:
            return default
        if not isinstance(raw, bool):
            raise ToolError(f"argument {key!r} must be true or false")
        return raw

    def uuid(self, key: str) -> uuid.UUID:
        raw = self.string(key)
        try:
            return uuid.UUID(raw)
        except ValueError:
            raise ToolError(f"argument {key!r} is not a valid id: {raw!r}") from None


@dataclass(frozen=True, slots=True)
class Blocks:
    """A handler result made of content blocks, sent to the agent as they are.

    Return it instead of a string or an object when the agent must get an image, a sound or a file.
    Build the blocks with ``TextContent``, ``ImageContent``, ``AudioContent`` and
    ``EmbeddedResource``. The size cap counts every block.
    """

    items: tuple[ContentBlock, ...]


# The handler returns text, a ``Blocks``, or anything ``msgspec`` can encode (a Struct, a
# dataclass, a dict). It is declared ``object`` because that is exactly the contract: msgspec
# decides, at the boundary.
type ToolOutput = object


@dataclass(frozen=True, slots=True)
class Tool[Ctx]:
    """One tool.

    ``Ctx`` is whatever the host passes to its handlers (the caller plus repositories).

    ``scope``: if set, the caller's token must carry it. ``visible``: if set, the tool is listed and
    callable only when it returns true for the caller's context (operator tools); a tool the caller
    cannot see answers as unknown, so its existence is not revealed.
    """

    name: str
    title: str
    effect: Effect
    description: str
    input_schema: JsonObject
    handler: Callable[[Ctx, Arguments], Awaitable[ToolOutput]]
    scope: str = ""
    visible: Callable[[Ctx], bool] | None = None

    def __post_init__(self) -> None:
        if not 0 < len(self.name) <= NAME_MAX:
            raise ValueError(f"tool name {self.name!r} must be 1-{NAME_MAX} characters")
        if not 0 < len(self.title) <= TITLE_MAX:
            raise ValueError(f"tool {self.name!r}: title must be 1-{TITLE_MAX} characters")
        if self.input_schema.get("type") != "object":
            raise ValueError(f"tool {self.name!r}: input_schema must be a JSON Schema object")

    def annotations(self) -> ToolAnnotations:
        if self.effect is Effect.READ:
            return ToolAnnotations(title=self.title, read_only_hint=True)
        return ToolAnnotations(title=self.title, destructive_hint=self.effect is Effect.DESTRUCTIVE)

    def descriptor(self) -> ToolDescriptor:
        return ToolDescriptor(
            name=self.name,
            title=self.title,
            description=self.description,
            input_schema=msgspec.Raw(msgspec.json.encode(self.input_schema)),
            annotations=self.annotations(),
        )

    def is_visible(self, ctx: Ctx) -> bool:
        return self.visible is None or self.visible(ctx)


# -- JSON Schema helpers: small, so a tool's schema stays readable -------------------------------


def string(description: str, *, enum: tuple[str, ...] = ()) -> JsonObject:
    schema: JsonObject = {"type": "string", "description": description}
    if enum:
        schema["enum"] = list(enum)
    return schema


def integer(
    description: str, *, minimum: int | None = None, maximum: int | None = None
) -> JsonObject:
    schema: JsonObject = {"type": "integer", "description": description}
    if minimum is not None:
        schema["minimum"] = minimum
    if maximum is not None:
        schema["maximum"] = maximum
    return schema


def boolean(description: str) -> JsonObject:
    return {"type": "boolean", "description": description}


def object_schema(
    properties: Mapping[str, JsonObject] | None = None, *, required: tuple[str, ...] = ()
) -> JsonObject:
    """A tool's ``input_schema``. ``required`` must name declared properties."""
    props = dict(properties or {})
    missing = [r for r in required if r not in props]
    if missing:
        raise ValueError(f"required names not declared as properties: {missing}")
    schema: JsonObject = {"type": "object", "properties": dict(props)}
    if required:
        schema["required"] = list(required)
    return schema
