"""DEF467 — Room, 1-on-1 and Brief streams must emit a keepalive while the model thinks.

A slow reasoning turn produced zero bytes for 300 s; the client could not tell a
slow turn from a dead one, and Cloudflare's ~100 s idle timeout can cut a silent
stream outright. `with_keepalive` (app/api/sse.py) interleaves an SSE comment frame
whenever the wrapped stream is quiet. Tests: the helper's behaviour, that cleanup of
the wrapped stream is unchanged, that the interval sits well under the proxy timeout,
and (structural) that every `StreamingResponse` under app/api wraps its body.
"""

from __future__ import annotations

import ast
import asyncio
import pathlib

from app.api.sse import (
    SSE_KEEPALIVE_FRAME,
    SSE_KEEPALIVE_INTERVAL_S,
    sse_json,
    with_keepalive,
)

_API = pathlib.Path(__file__).resolve().parents[2] / "app" / "api"


async def _collect(agen):
    return [f async for f in agen]


def test_quiet_stream_gets_keepalives_and_real_frames_pass_through_in_order():
    real_first = sse_json("started", '{"a": 1}')
    real_last = sse_json("done", '{"b": 2}')

    async def slow():
        yield real_first
        await asyncio.sleep(0.35)  # model "thinking"
        yield real_last

    frames = asyncio.run(_collect(with_keepalive(slow(), interval=0.1)))
    assert frames[0] == real_first
    assert frames[-1] == real_last
    assert frames.count(SSE_KEEPALIVE_FRAME) >= 2
    assert set(frames[1:-1]) == {SSE_KEEPALIVE_FRAME}


def test_a_busy_stream_gets_no_keepalive():
    async def busy():
        for i in range(5):
            yield sse_json("agent_token", f'{{"i": {i}}}')

    frames = asyncio.run(_collect(with_keepalive(busy(), interval=5.0)))
    assert SSE_KEEPALIVE_FRAME not in frames
    assert len(frames) == 5


def test_keepalive_is_an_sse_comment_not_an_event():
    assert SSE_KEEPALIVE_FRAME.startswith(":")
    assert "event:" not in SSE_KEEPALIVE_FRAME and "data:" not in SSE_KEEPALIVE_FRAME
    assert SSE_KEEPALIVE_FRAME.endswith("\n\n")


def test_interval_is_well_under_the_cloudflare_idle_timeout():
    assert SSE_KEEPALIVE_INTERVAL_S <= 20.0


def test_closing_the_wrapper_runs_the_wrapped_streams_finally():
    """The 1-on-1 / Brief concurrency slot is released in `event_stream`'s
    `finally`; wrapping must not strand it when the client disconnects."""
    cleaned: list[bool] = []

    async def inner():
        try:
            yield sse_json("started", "{}")
            await asyncio.sleep(30)
            yield sse_json("done", "{}")
        finally:
            cleaned.append(True)

    async def go():
        wrapped = with_keepalive(inner(), interval=0.05)
        assert await wrapped.__anext__() == sse_json("started", "{}")
        assert await wrapped.__anext__() == SSE_KEEPALIVE_FRAME
        await wrapped.aclose()

    asyncio.run(go())
    assert cleaned == [True]


def test_an_exception_in_the_wrapped_stream_still_propagates():
    async def boom():
        yield sse_json("started", "{}")
        raise RuntimeError("stream broke")

    async def go():
        try:
            await _collect(with_keepalive(boom(), interval=1.0))
        except RuntimeError as e:
            return str(e)

    assert asyncio.run(go()) == "stream broke"


def test_every_streaming_response_under_app_api_is_wrapped():
    found = 0
    for path in sorted(_API.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "StreamingResponse"
            ):
                continue
            found += 1
            body = node.args[0] if node.args else None
            assert (
                isinstance(body, ast.Call)
                and isinstance(body.func, ast.Name)
                and body.func.id == "with_keepalive"
            ), f"{path.name}:{node.lineno} streams without a keepalive (DEF467)"
    assert found >= 4  # room x2, one_on_one, brief — the guard is not vacuous
