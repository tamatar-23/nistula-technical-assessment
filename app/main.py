"""FastAPI application — webhook endpoint for Nistula guest messages.

Flow:
1. POST /webhook/message receives a raw guest message payload.
2. The payload is normalised into a unified, channel-independent schema.
3. The normalised message is sent to Claude (or a mock) to draft a reply.
4. A deterministic confidence score and routing action are attached.
5. The response is returned to the caller.
"""

from fastapi import FastAPI, HTTPException

from app.claude_client import ClaudeClientError, draft_reply_with_claude
from app.confidence import calculate_confidence, choose_action
from app.models import InboundMessage, WebhookResponse
from app.normalizer import normalize_message

app = FastAPI(
    title="Nistula Guest Message Handler",
    version="1.0.0",
    description="Webhook service that normalises guest messages and drafts AI replies.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Lightweight liveness probe."""
    return {"status": "ok"}


@app.post("/webhook/message", response_model=WebhookResponse)
async def handle_message(payload: InboundMessage) -> WebhookResponse:
    """Accept a guest message, draft an AI reply, and return it with a
    confidence score and routing action.

    Error responses:
        422 — invalid or missing payload fields (handled by FastAPI).
        502 — Claude API failure or configuration error.
    """
    unified_message = normalize_message(payload)

    try:
        drafted_reply = await draft_reply_with_claude(unified_message)
    except ClaudeClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    confidence_score = calculate_confidence(unified_message, drafted_reply)
    action = choose_action(unified_message.query_type, confidence_score)

    return WebhookResponse(
        message_id=unified_message.message_id,
        query_type=unified_message.query_type,
        drafted_reply=drafted_reply,
        confidence_score=confidence_score,
        action=action,
    )
