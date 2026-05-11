"""Claude API client — builds the prompt, calls the API, and returns the draft.

When ``USE_MOCK_CLAUDE=true`` the real API is bypassed and a deterministic
mock reply is returned instead, so the full pipeline can be tested
without consuming API credits.
"""

import httpx

from app.config import settings
from app.models import QueryType, UnifiedMessage
from app.property_context import PROPERTY_CONTEXT


class ClaudeClientError(RuntimeError):
    """Raised when the Claude API call fails or returns an unusable response."""


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_prompt(message: UnifiedMessage) -> str:
    """Assemble the user-role prompt sent to Claude.

    The prompt includes:
    - Reply-style instructions (warm, concise, operationally safe).
    - The full Villa B1 property context from the brief.
    - All normalised message fields so the model has full situational awareness.
    """
    return f"""\
You are drafting a concise, warm reply for Nistula's guest messaging team.
Do not claim that a booking or refund is confirmed unless the context says so.
If the message is a complaint or operational emergency, be empathetic and say \
the team is escalating it immediately.

Property context:
{PROPERTY_CONTEXT}

Inbound message:
- Guest name: {message.guest_name}
- Source: {message.source.value}
- Booking reference: {message.booking_ref or "not provided"}
- Property ID: {message.property_id}
- Query type: {message.query_type.value}
- Message: {message.message_text}

Draft only the reply text. Keep it under 120 words."""


# ---------------------------------------------------------------------------
# Mock client (for offline testing)
# ---------------------------------------------------------------------------


def _mock_draft_reply(message: UnifiedMessage) -> str:
    """Return a hardcoded reply based on the classified query type.

    Each reply mirrors what the real model would produce for the
    property context given in the assessment brief.
    """
    first_name = message.guest_name.split()[0]

    replies = {
        QueryType.pre_sales_availability: (
            f"Hi {first_name}! Great news, Villa B1 is available from April 20 to 24. "
            "For 2 adults, the base rate is INR 18,000 per night. "
            "I can help you proceed with the booking if these dates work for you."
        ),
        QueryType.pre_sales_pricing: (
            f"Hi {first_name}, Villa B1 is INR 18,000 per night for up to 4 guests. "
            "Extra guests are INR 2,000 per person per night. "
            "Share your dates and guest count and we can confirm the total."
        ),
        QueryType.post_sales_checkin: (
            f"Hi {first_name}, check-in is from 2pm and check-out is by 11am. "
            "The WiFi password is Nistula@2024, and the caretaker is available "
            "from 8am to 10pm."
        ),
        QueryType.special_request: (
            f"Hi {first_name}, we can help with special requests such as chef "
            "service or transfers. Chef service needs pre-booking, so please "
            "share your preferred timing and details."
        ),
        QueryType.complaint: (
            f"Hi {first_name}, I am really sorry about this. I am escalating it "
            "to the on-call team immediately so they can help resolve it as "
            "quickly as possible."
        ),
    }

    return replies.get(
        message.query_type,
        f"Hi {first_name}, thanks for reaching out. Villa B1 is a 3-bedroom "
        "villa in Assagao with a private pool and space for up to 6 guests. "
        "Please share what you would like to know.",
    )


# ---------------------------------------------------------------------------
# Real client
# ---------------------------------------------------------------------------


async def draft_reply_with_claude(message: UnifiedMessage) -> str:
    """Send the normalised message to Claude and return the drafted reply.

    Falls back to ``_mock_draft_reply`` when ``USE_MOCK_CLAUDE`` is enabled.

    Raises:
        ClaudeClientError: On missing API key, HTTP errors, or empty responses.
    """
    if settings.use_mock_claude:
        return _mock_draft_reply(message)

    if not settings.anthropic_api_key:
        raise ClaudeClientError(
            "ANTHROPIC_API_KEY is not configured. "
            "Set it in .env or enable USE_MOCK_CLAUDE=true."
        )

    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": settings.anthropic_model,
        "max_tokens": 350,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": build_prompt(message)}],
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                settings.anthropic_api_url, headers=headers, json=body
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ClaudeClientError(
            f"Claude API returned {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ClaudeClientError("Could not reach Claude API") from exc

    data = response.json()
    content = data.get("content", [])
    text_blocks = [
        block.get("text", "") for block in content if block.get("type") == "text"
    ]
    drafted_reply = "\n".join(text_blocks).strip()

    if not drafted_reply:
        raise ClaudeClientError("Claude API response did not include reply text")

    return drafted_reply
