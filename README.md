# litestar-mcp-server

[![pipeline status](https://gitlab.com/cardona-oss/litestar-mcp-server/badges/main/pipeline.svg)](https://gitlab.com/cardona-oss/litestar-mcp-server/-/pipelines)
[![PyPI version](https://img.shields.io/pypi/v/litestar-mcp-server.svg)](https://pypi.org/project/litestar-mcp-server/)
[![Python versions](https://img.shields.io/pypi/pyversions/litestar-mcp-server.svg)](https://pypi.org/project/litestar-mcp-server/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A small MCP server for Litestar, with no SDK: tools with titles, read or destructive hints and scopes, over streamable HTTP

## Install

```bash
pip install litestar-mcp-server
```

Requires Python 3.12+.

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

## Why litestar-mcp-server

An MCP endpoint for a SaaS product is a small thing: JSON-RPC over one POST route. The official SDK
mounts a second web stack with its own auth and lifespan. This library is the small thing, as a
normal Litestar route, so auth, dependency injection and logging are the ones your app already has.
It also makes the connector-directory rules hard to forget: every tool needs a title of at most 64
characters and an effect, and the hints come from the effect.

## Key features

- Stateless streamable HTTP (2025-11-25, 2025-06-18, 2025-03-26): one JSON object per POST, 405 on GET.
- `Effect.READ`, `ADDITIVE` or `DESTRUCTIVE` per tool, giving `readOnlyHint` or `destructiveHint`.
- `title` at the top level and in `annotations`.
- Per-tool `scope`, and per-caller `visible` (operator tools do not exist for others).
- Failures reach the agent as readable results; unexpected errors never leak details.
- A cap on result size, so a tool cannot dump a database.
- Typed argument getters, tiny JSON Schema helpers, frozen dataclasses throughout.
- No SDK and no pydantic: Litestar and msgspec only.

Not included: resources, prompts, SSE streams, sessions. Tools only.

## Links

- **Documentation:** https://cardona-oss.gitlab.io/litestar-mcp-server/
- **Source:** https://gitlab.com/cardona-oss/litestar-mcp-server
- **Issues:** https://gitlab.com/cardona-oss/litestar-mcp-server/-/issues
- **PyPI:** https://pypi.org/project/litestar-mcp-server/
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)

## Contributing

Developer setup, the dev loop, and the release process live in
[CONTRIBUTING.md](CONTRIBUTING.md). In short: `uv sync && make install-hooks`, then
`make check` runs the same gate CI runs.

## License

MIT © 2026 Jorge Cardona (see [LICENSE](LICENSE)).
