---
title: "Move paas's MCP controller onto litestar-mcp-server"
status: open
scope: M
owner: null
filed: 2026-11-21
area: interop
verify: test
blocked_by: null
fixed_in: null
---

paas has controllers/mcp.py (235 lines) and 1,900 lines of tools. Done: paas imports McpServer, its MCP tests pass, effects are set on every tool (deploy, scale, rollback, run_job destructive).
