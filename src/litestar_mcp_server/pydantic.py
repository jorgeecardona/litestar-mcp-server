"""Tools whose arguments are a pydantic model (extra ``pydantic``).

``model_tool`` builds a ``Tool`` from a model: the model gives the ``input_schema`` and checks the
arguments, and the handler receives the model instance instead of ``Arguments``. Install it with
``pip install "litestar-mcp-server[pydantic]"``. The rest of the package does not import pydantic.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ValidationError

from litestar_mcp_server.tools import Arguments, Effect, Tool, ToolError, ToolOutput


def model_tool[Ctx, M: BaseModel](  # noqa: PLR0913 (the fields of ``Tool``, by keyword)
    *,
    name: str,
    title: str,
    effect: Effect,
    description: str,
    model: type[M],
    handler: Callable[[Ctx, M], Awaitable[ToolOutput]],
    scope: str = "",
    visible: Callable[[Ctx], bool] | None = None,
) -> Tool[Ctx]:
    """A ``Tool`` whose arguments are validated by ``model``.

    The ``input_schema`` is ``model.model_json_schema()``: field descriptions, bounds and enums
    reach the agent. Wrong arguments become a ``ToolError`` that names each field and what is wrong
    with it, and never repeats the value sent.
    """

    async def run(ctx: Ctx, args: Arguments) -> ToolOutput:
        try:
            parsed = model.model_validate(dict(args.values))
        except ValidationError as error:
            raise ToolError(_readable(error)) from None
        return await handler(ctx, parsed)

    return Tool(
        name=name,
        title=title,
        effect=effect,
        description=description,
        input_schema=model.model_json_schema(),
        handler=run,
        scope=scope,
        visible=visible,
    )


def _readable(error: ValidationError) -> str:
    problems = [
        f"{'.'.join(str(part) for part in issue['loc']) or 'arguments'}: {issue['msg']}"
        for issue in error.errors(include_url=False, include_context=False, include_input=False)
    ]
    return "invalid arguments: " + "; ".join(problems)
