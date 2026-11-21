"""The Litestar shell: one route at ``path`` that feeds ``McpServer.handle``.

    mcp = mcp_handlers(
        server,
        path="/mcp",
        guards=[bearer_guard(...)],                       # authentication (401 before anything else)
        dependencies={"mcp_context": Provide(build_ctx)}, # your Ctx, built with Litestar's own DI
        scopes=lambda request: verified_token(request).scopes,   # optional
    )
    app = Litestar([*mcp, ...])

The context is a normal Litestar dependency named ``mcp_context``, so repositories, sessions and
the current user come from the same injection every other route uses.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from litestar import Request, Response, get, post
from litestar.di import NamedDependency
from litestar.handlers import HTTPRouteHandler

from litestar_mcp_server.server import McpServer

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection
    from litestar.di import Provide
    from litestar.handlers.base import BaseRouteHandler

type McpGuard = Callable[
    [ASGIConnection[Any, Any, Any, Any], BaseRouteHandler], Awaitable[None] | None
]
"""A Litestar guard function; pass it in ``guards=[...]``."""

ScopesGetter = Callable[[Request[Any, Any, Any]], frozenset[str] | None]


def mcp_handlers[Ctx](
    server: McpServer[Ctx],
    *,
    path: str = "/mcp",
    guards: Sequence[McpGuard] = (),
    dependencies: Mapping[str, Provide] | None = None,
    scopes: ScopesGetter | None = None,
) -> list[HTTPRouteHandler]:
    """The GET (405) and POST handlers for ``server`` at ``path``."""

    @get(path, guards=list(guards), include_in_schema=False)
    async def no_stream() -> Response[None]:
        # A server offering no server-initiated SSE stream MUST answer GET with 405.
        return Response(None, status_code=405)

    @post(
        path,
        guards=list(guards),
        dependencies=dict(dependencies or {}),
        status_code=200,
        include_in_schema=False,
    )
    async def rpc(
        request: Request[Any, Any, Any],
        mcp_context: NamedDependency[Any],
    ) -> Response[bytes]:
        headers = {k.lower(): v for k, v in request.headers.items()}
        answer = await server.handle(
            body=await request.body(),
            headers=headers,
            ctx=mcp_context,
            scopes=scopes(request) if scopes is not None else None,
        )
        return Response(answer.body, status_code=answer.status, media_type=answer.media_type)

    return [no_stream, rpc]
