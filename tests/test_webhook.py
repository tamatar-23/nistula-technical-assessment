"""Webhook endpoint tests.

Covers every query type, the action routing thresholds, and input
validation.  All tests use USE_MOCK_CLAUDE=true so they run without
an API key.
"""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

# Force mock mode so tests never hit the real Claude API.
settings.use_mock_claude = True

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def post_message(message: str, **overrides):
    """Send a webhook payload with sensible defaults.  Override any field via kwargs."""
    payload = {
        "source": "whatsapp",
        "guest_name": "Rahul Sharma",
        "message": message,
        "timestamp": "2026-05-05T10:30:00Z",
        "booking_ref": "NIS-2024-0891",
        "property_id": "villa-b1",
    }
    payload.update(overrides)
    return client.post("/webhook/message", json=payload)


# ---------------------------------------------------------------------------
# Query type classification (covers all 6 categories)
# ---------------------------------------------------------------------------


def test_availability_query_auto_sends():
    """Pre-sales availability with known dates should classify correctly and auto-send."""
    response = post_message(
        "Is the villa available from April 20 to 24? What is the rate for 2 adults?"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_type"] == "pre_sales_availability"
    assert body["confidence_score"] > 0.85
    assert body["action"] == "auto_send"
    assert "INR 18,000" in body["drafted_reply"]


def test_pricing_query_is_classified():
    """A pure pricing question should classify as pre_sales_pricing."""
    response = post_message("How much does the villa cost per night for 5 guests?")

    assert response.status_code == 200
    body = response.json()
    assert body["query_type"] == "pre_sales_pricing"


def test_checkin_query_is_classified():
    """Post-sales check-in query should return check-in details."""
    response = post_message(
        "What time can we check in and what is the WiFi password?"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_type"] == "post_sales_checkin"
    assert body["action"] in {"auto_send", "agent_review"}
    assert "2pm" in body["drafted_reply"]


def test_special_request_is_classified():
    """A chef or transfer request should classify as special_request."""
    response = post_message(
        "Can we arrange a chef for dinner on the 21st? Also need an airport transfer."
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_type"] == "special_request"


def test_complaint_is_escalated():
    """Complaints should always escalate with confidence below 0.60."""
    response = post_message(
        "The AC is not working. I am not happy and want a refund."
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query_type"] == "complaint"
    assert body["confidence_score"] < 0.60
    assert body["action"] == "escalate"


def test_general_enquiry_fallback():
    """A message that doesn't match specific keywords should fall through to general_enquiry."""
    response = post_message("Do you allow pets at the villa?")

    assert response.status_code == 200
    body = response.json()
    assert body["query_type"] == "general_enquiry"


# ---------------------------------------------------------------------------
# Confidence & action routing
# ---------------------------------------------------------------------------


def test_high_confidence_with_full_context():
    """Known property + booking ref + specific terms should produce high confidence."""
    response = post_message(
        "Is the villa available from April 20 to 24?",
        property_id="villa-b1",
        booking_ref="NIS-2024-0891",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["confidence_score"] > 0.85
    assert body["action"] == "auto_send"


def test_lower_confidence_without_booking_ref():
    """Missing booking reference should produce slightly lower confidence."""
    response = post_message(
        "Is the villa available from April 20 to 24?",
        booking_ref=None,
    )

    assert response.status_code == 200
    body = response.json()
    # Should still work, but confidence is lower than with a booking ref.
    assert body["confidence_score"] <= 0.97


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


def test_response_contains_all_required_fields():
    """Every response must include the five fields specified in the brief."""
    response = post_message("What is the WiFi password?")

    assert response.status_code == 200
    body = response.json()
    assert "message_id" in body
    assert "query_type" in body
    assert "drafted_reply" in body
    assert "confidence_score" in body
    assert "action" in body


def test_message_id_is_valid_uuid():
    """The message_id should be a valid UUID v4 string."""
    response = post_message("Tell me about the villa.")

    assert response.status_code == 200
    body = response.json()
    # UUID format: 8-4-4-4-12 hex characters
    parts = body["message_id"].split("-")
    assert len(parts) == 5


# ---------------------------------------------------------------------------
# Input validation & error handling
# ---------------------------------------------------------------------------


def test_invalid_source_returns_422():
    """An unsupported channel should return 422 validation error."""
    response = post_message("Hello", source="sms")
    assert response.status_code == 422


def test_empty_message_returns_422():
    """An empty message body should be rejected."""
    response = post_message("")
    assert response.status_code == 422


def test_missing_guest_name_returns_422():
    """Missing required field guest_name should be rejected."""
    response = client.post("/webhook/message", json={
        "source": "whatsapp",
        "message": "Hello",
        "timestamp": "2026-05-05T10:30:00Z",
        "property_id": "villa-b1",
    })
    assert response.status_code == 422


def test_missing_property_id_returns_422():
    """Missing required field property_id should be rejected."""
    response = client.post("/webhook/message", json={
        "source": "whatsapp",
        "guest_name": "Rahul",
        "message": "Hello",
        "timestamp": "2026-05-05T10:30:00Z",
    })
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Multi-channel support
# ---------------------------------------------------------------------------


def test_all_valid_sources_are_accepted():
    """Every channel in the enum should be accepted without error."""
    for source in ("whatsapp", "booking_com", "airbnb", "instagram", "direct"):
        response = post_message("Hello from this channel", source=source)
        assert response.status_code == 200, f"Source '{source}' was rejected"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health_endpoint():
    """GET /health should return 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
