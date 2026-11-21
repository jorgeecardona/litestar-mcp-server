# AGENTS.md

Guidance for AI coding agents working in this repo. Humans: read README.md and CHANGELOG.md.

## Overview

litestar-mcp-server: A small MCP server for Litestar, with no SDK: tools with titles, read or destructive hints and scopes, over streamable HTTP.

Layout: `protocol.py` (msgspec frames), `tools.py` (`Tool`, `Effect`, `Arguments`, schema helpers),
`server.py` (`McpServer`, no HTTP), `plugin.py` (`mcp_handlers`, the Litestar routes). Extracted from
the hand-written MCP in tyko and paas. Plan: `../../MCP-PLAN.md`, `../../MCP-CONNECTORS.md`.

## Build

- `uv sync` installs dependencies. Toolchain (moon, uv) is pinned in `.prototools`; `proto install` brings it up.
- `make install-hooks` once, to enable the tracked git hooks.

## Test

- `make test` runs the suite.
- `make check` runs lint + typecheck + test (the same stage CI runs via `moon run :ci`).
- Everything in `make check` must pass before you commit.

## Style

- Format and autofix: `make format` (ruff, line length 100).
- Lint: `make lint`. Types: `make typecheck` (pyright strict on `src/`).
- Prefer frozen dataclasses and explicit types. Keep the public API typed (`py.typed`).

## Gotchas

- Keep the directory rules true by construction: every tool has a title (64 characters max) and an
  effect; a write tool never carries `readOnlyHint`. Add a test for any new rule.
- A tool the caller may not see must answer as unknown, never as forbidden.
- No SDK and no pydantic. Do not add either.
- `msgspec` cannot decode PEP 695 recursive aliases (RecursionError on 0.22), so tool arguments are
  decoded untyped at the boundary and wrapped in `Arguments`.
- Version lives as `__version__` in `src/litestar_mcp_server/__init__.py`; `pyproject.toml` reads it via `[tool.hatch.version]` (`version` is `dynamic`). The pre-commit hook auto-bumps it when `src/` changes. Do not edit versions by hand elsewhere.
- Record follow-ups in `docs/issues/`, not as scattered TODO comments.
