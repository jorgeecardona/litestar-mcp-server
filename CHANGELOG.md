# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.5]

### Added

- Extra `pydantic`: `model_tool` (in `litestar_mcp_server.pydantic`) builds a tool from a pydantic
  model. The model gives the input schema and checks the arguments, and the handler gets the model.

## [0.0.4]

### Changed

- A tool that is not read-only now sends `readOnlyHint: false` as well as `destructiveHint`. The
  Claude directory's form flags every write tool that lacks `readOnlyHint` (seen 2026-11-21 on tyko:
  8 suggestions).

## [0.0.3]

### Added

- `AudioContent` and `EmbeddedResource` (with `BlobResource`): a tool can return a sound or any
  binary file, such as a PDF or a zip.

## [0.0.2]

### Added

- `Blocks`, `TextContent` and `ImageContent`: a tool can return text and pictures to the agent.

## [0.0.1]

### Added

- `McpServer` with `initialize`, `ping`, `tools/list` and `tools/call`; protocol version negotiation.
- `Tool` with `title`, `effect` (read, additive, destructive), `scope` and `visible`.
- `mcp_handlers`: the Litestar GET (405) and POST routes, with guards, dependencies and a scopes getter.
- `Arguments` typed getters, JSON Schema helpers, a result size cap.
