"""1-on-1 chat endpoints. POST to start, POST to send messages (SSE stream back)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas.one_on_one import (
    OneOnOneMessageRequest,
    OneOnOneSession,
    OneOnOneStartRequest,
)
from app.services.agent_runner import AgentRunner, get_agent_runner, hydrate_mandate

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.post(
    "/one_on_one/start",
    response_model=OneOnOneSession,
    status_code=status.HTTP_201_CREATED,
)
async def start_one_on_one(
    req: OneOnOneStartRequest,
    runner: AgentRunner = Depends(get_agent_runner),
) -> OneOnOneSession:
    mandate = hydrate_mandate(req.mandate_override)
    # Ensure the locale on the mandate matches the request
    mandate = mandate.model_copy(update={"locale": req.locale})
    return runner.open_one_on_one(agent_id=req.agent_id, mandate=mandate)


@router.post("/one_on_one/message")
async def send_message(
    req: OneOnOneMessageRequest,
    runner: AgentRunner = Depends(get_agent_runner),
) -> StreamingResponse:
    """Send a user message; the response streams back as Server-Sent Events.

    Each event payload is a single content chunk (text). The stream ends with
    `event: done\\ndata: {...}` containing minimal stats.
    """
    session = runner.get_session(req.session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")

    async def event_stream():
        total_chars = 0
        try:
            async for chunk in runner.stream_one_on_one_message(
                session=session,
                history=req.history,
                user_message=req.user_message,
            ):
                total_chars += len(chunk)
                # SSE event format
                # Escape backslashes + newlines so the line stays valid
                safe = chunk.replace("\\", "\\\\").replace("\n", "\\n")
                yield f"event: token\ndata: {safe}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {str(e)[:300]}\n\n"
        finally:
            yield f"event: done\ndata: {{\"chars\": {total_chars}}}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/one_on_one/{session_id}", response_model=OneOnOneSession)
async def get_one_on_one(
    session_id: UUID,
    runner: AgentRunner = Depends(get_agent_runner),
) -> OneOnOneSession:
    session = runner.get_session(session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    return session
