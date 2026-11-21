---
title: "Move tyko's hand-written MCP onto litestar-mcp-server"
status: open
scope: M
owner: null
filed: 2026-11-21
area: interop
verify: test
blocked_by: null
fixed_in: null
---

Tyko has mcp_protocol.py (179 lines) and controllers/mcp.py (145 lines); the tool layer stays in tyko. Done: tyko imports McpServer, its 56 MCP tests still pass, mcp_protocol.py is deleted.
