---
title: "Check whether the directory accepts destructiveHint false on additive tools"
status: open
scope: XS
owner: null
filed: 2026-11-21
area: interop
verify: probe
blocked_by: null
fixed_in: null
---

Directory pages say each tool needs readOnlyHint true or destructiveHint true. Effect.ADDITIVE emits destructiveHint false. Done: run the MCP Inspector and the directory scan on one additive tool and record whether it passes; if not, make ADDITIVE emit true.
