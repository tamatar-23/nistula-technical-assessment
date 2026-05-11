"""Converts raw inbound payloads into the channel-independent unified schema."""

from uuid import uuid4

from app.classifier import classify_query
from app.models import InboundMessage, UnifiedMessage


def normalize_message(payload: InboundMessage) -> UnifiedMessage:
    """Create a ``UnifiedMessage`` from a raw webhook payload.

    Steps:
    1. Generate a unique message ID.
    2. Strip whitespace from free-text fields.
    3. Classify the guest's intent via keyword matching.
    """
    return UnifiedMessage(
        message_id=uuid4(),
        source=payload.source,
        guest_name=payload.guest_name.strip(),
        message_text=payload.message.strip(),
        timestamp=payload.timestamp,
        booking_ref=payload.booking_ref.strip() if payload.booking_ref else None,
        property_id=payload.property_id.strip(),
        query_type=classify_query(payload.message),
    )
