# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `McpServer` with `initialize`, `ping`, `tools/list` and `tools/call`; protocol version negotiation.
- `Tool` with `title`, `effect` (read, additive, destructive), `scope` and `visible`.
- `mcp_handlers`: the Litestar GET (405) and POST routes, with guards, dependencies and a scopes getter.
- `Arguments` typed getters, JSON Schema helpers, a result size cap.
