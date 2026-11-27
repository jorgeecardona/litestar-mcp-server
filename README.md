<h1 align="center">litestar-mcp-server</h1>

<p align="center"><strong>Add MCP tools to a Litestar app as a route, with the auth and dependency injection the app already has.</strong></p>

<p align="center">
  <a href="https://pypi.org/project/litestar-mcp-server/"><img alt="PyPI" src="https://img.shields.io/pypi/v/litestar-mcp-server?style=flat-square"></a>
  <a href="https://pypi.org/project/litestar-mcp-server/"><img alt="Python versions" src="https://img.shields.io/pypi/pyversions/litestar-mcp-server?style=flat-square"></a>
  <a href="https://gitlab.com/cardona-oss/litestar-mcp-server/-/pipelines"><img alt="Pipeline" src="https://img.shields.io/gitlab/pipeline-status/cardona-oss%2Flitestar-mcp-server?branch=main&style=flat-square"></a>
  <a href="https://gitlab.com/cardona-oss/litestar-mcp-server/-/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue?style=flat-square"></a>
</p>

<p align="center">
  <a href="https://gitlab.com/cardona-oss/litestar-mcp-server/-/blob/main/README.md#quickstart">Quickstart</a> ·
  <a href="https://gitlab.com/cardona-oss/litestar-mcp-server/-/blob/main/README.md#why-litestar-mcp-server">Why litestar-mcp-server</a> ·
  <a href="https://gitlab.com/cardona-oss/litestar-mcp-server/-/blob/main/CHANGELOG.md">Changelog</a>
</p>

---

## Overview

Route handlers that serve MCP tools from a Litestar app over streamable HTTP, without the MCP SDK. Tools have
titles, read or destructive hints and scopes. Auth and dependency injection are the ones the
app already uses.

Status: beta.

## Install

```bash
pip install litestar-mcp-server
```

Requires Python 3.12+. To write a tool's arguments as a pydantic model, add the extra:

```bash
pip install "litestar-mcp-server[pydantic]"
```

## Quickstart

```python
from dataclasses import dataclass
from litestar import Litestar
from litestar.di import Provide
from litestar_mcp_server import (
    Arguments, Effect, McpConfig, McpServer, Tool, mcp_handlers, object_schema, string,
)

@dataclass(frozen=True, slots=True)
class Ctx:  # whatever your tools need about the caller
    user: str

async def add_note(ctx: Ctx, args: Arguments) -> str:
    return f"added {args.string('text')!r} for {ctx.user}"

server = McpServer(
    config=McpConfig(name="notes", version="0.1.0"),
    tools=[Tool(
        name="add_note", title="Add a note", effect=Effect.ADDITIVE,
        description="Add a note for the signed-in user.",
        input_schema=object_schema({"text": string("the note")}, required=("text",)),
        handler=add_note, scope="notes:write",
    )],
)

async def build_ctx() -> Ctx:  # a normal Litestar dependency
    return Ctx(user="demo")

app = Litestar(mcp_handlers(server, dependencies={"mcp_context": Provide(build_ctx)}))
```

Add `guards=[...]` for authentication and `scopes=lambda request: ...` so a tool's `scope` is
checked. With [litestar-oauth-server](https://pypi.org/project/litestar-oauth-server/) those are
`bearer_guard(...)` and `verified_token(request).scopes`. See `examples/basic.py`.

## Arguments as a pydantic model

`model_tool` (from `litestar_mcp_server.pydantic`, needs the extra) takes a model instead of a
hand-written schema. The model gives the `input_schema` and checks the arguments, and the handler
gets the model.

```python
from pydantic import BaseModel, Field
from litestar_mcp_server import Effect
from litestar_mcp_server.pydantic import model_tool

class AddNote(BaseModel):
    text: str = Field(min_length=1, description="the note")

async def add_note(ctx: Ctx, args: AddNote) -> str:
    return f"added {args.text!r} for {ctx.user}"

tool = model_tool(
    name="add_note", title="Add a note", effect=Effect.ADDITIVE,
    description="Add a note for the signed-in user.", model=AddNote, handler=add_note,
)
```

Wrong arguments reach the agent as one readable line per field, for example
`invalid arguments: text: String should have at least 1 character`. The value sent is not repeated.

## Why litestar-mcp-server

An MCP endpoint for a SaaS product is a small thing: JSON-RPC over one POST route. The official SDK
mounts a second web stack with its own auth and lifespan. This library is the small thing, as a
normal Litestar route, so auth, dependency injection and logging are the ones your app already has.
It also makes the connector-directory rules hard to forget: every tool needs a title of at most 64
characters and an effect, and the hints come from the effect.

Use the official SDK when you need resources, prompts, SSE streams or sessions. This library
has tools only.

## Key features

- Stateless streamable HTTP (2025-11-25, 2025-06-18, 2025-03-26): one JSON object per POST, 405 on GET.
- `Effect.READ`, `ADDITIVE` or `DESTRUCTIVE` per tool, giving `readOnlyHint: true`, or
  `readOnlyHint: false` with `destructiveHint`.
- `title` at the top level and in `annotations`.
- Per-tool `scope`, and per-caller `visible` (operator tools do not exist for others).
- A tool can return text, images, sound or any binary file (`Blocks` of `TextContent`,
  `ImageContent`, `AudioContent`, `EmbeddedResource`).
- Failures reach the agent as readable results; unexpected errors never leak details.
- A cap on result size, so a tool cannot dump a database.
- Typed argument getters, tiny JSON Schema helpers, frozen dataclasses throughout.
- No SDK. Litestar and msgspec only; pydantic is an optional extra.

## Limits

- Resources, prompts, SSE streams and sessions are not built. Tools only.
- The stateless protocol (one POST per call) means no server-initiated messages.

## Links

- Repository: <https://gitlab.com/cardona-oss/litestar-mcp-server>
- PyPI: <https://pypi.org/project/litestar-mcp-server/>
- Changelog: [CHANGELOG.md](https://gitlab.com/cardona-oss/litestar-mcp-server/-/blob/main/CHANGELOG.md)

## Contributing

Developer setup, the dev loop, and the release process live in
[CONTRIBUTING.md](https://gitlab.com/cardona-oss/litestar-mcp-server/-/blob/main/CONTRIBUTING.md). In short: `uv sync && make install-hooks`, then
`make check` runs the same gate CI runs.

## License

MIT © Jorge Cardona (see [LICENSE](https://gitlab.com/cardona-oss/litestar-mcp-server/-/blob/main/LICENSE)).
