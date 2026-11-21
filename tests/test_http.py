import json
from collections.abc import Iterator
from typing import Any

import pytest
from litestar import Litestar, Request
from litestar.di import Provide
from litestar.exceptions import NotAuthorizedException
from litestar.testing import TestClient

from litestar_mcp_server import McpServer, mcp_handlers
from tests.conftest import Ctx

TOKENS = {"read": frozenset({"things:read"}), "write": frozenset({"things:read", "things:write"})}


async def guard(connection: Any, _handler: Any) -> None:
    token = connection.headers.get("authorization", "").removeprefix("Bearer ")
    if token not in TOKENS:
        raise NotAuthorizedException(headers={"WWW-Authenticate": 'Bearer resource_metadata="x"'})
    connection.scope["state"]["scopes"] = TOKENS[token]
    connection.scope["state"]["user"] = token


async def build_ctx(request: Request[Any, Any, Any]) -> Ctx:
    return Ctx(user=request.scope["state"]["user"])


@pytest.fixture
def client(server: McpServer[Ctx]) -> Iterator[TestClient[Any]]:
    handlers = mcp_handlers(
        server,
        path="/mcp",
        guards=[guard],
        dependencies={"mcp_context": Provide(build_ctx)},
        scopes=lambda request: request.scope["state"]["scopes"],
    )
    with TestClient(Litestar(handlers)) as test_client:
        yield test_client


def rpc(
    client: TestClient[Any], token: str, method: str, params: dict[str, Any] | None = None
) -> Any:
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        headers={"authorization": f"Bearer {token}"},
    )


def test_no_token_is_401_before_anything_else(client: TestClient[Any]) -> None:
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert response.status_code == 401
    assert "resource_metadata" in response.headers["www-authenticate"]


def test_get_is_405(client: TestClient[Any]) -> None:
    assert client.get("/mcp", headers={"authorization": "Bearer read"}).status_code == 405


def test_context_comes_from_litestar_dependencies(client: TestClient[Any]) -> None:
    response = rpc(client, "read", "tools/call", {"name": "list_things", "arguments": {}})
    text = response.json()["result"]["content"][0]["text"]
    assert json.loads(text)["owner"] == "read"


def test_read_token_cannot_call_a_write_tool(client: TestClient[Any]) -> None:
    params = {"name": "create_thing", "arguments": {"name": "n"}}
    assert rpc(client, "read", "tools/call", params).json()["result"]["isError"] is True
    assert rpc(client, "write", "tools/call", params).json()["result"]["isError"] is False


def test_protocol_header_is_checked_over_http(client: TestClient[Any]) -> None:
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        headers={"authorization": "Bearer read", "MCP-Protocol-Version": "1999-01-01"},
    )
    assert response.status_code == 400


def test_notification_over_http_is_202(client: TestClient[Any]) -> None:
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers={"authorization": "Bearer read"},
    )
    assert response.status_code == 202
