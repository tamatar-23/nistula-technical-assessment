"""Pydantic models for inbound payloads, internal schema, and API responses."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MessageSource(str, Enum):
    """Channels Nistula receives guest messages from."""

    whatsapp = "whatsapp"
    booking_com = "booking_com"
    airbnb = "airbnb"
    instagram = "instagram"
    direct = "direct"


class QueryType(str, Enum):
    """Categories every inbound message is classified into."""

    pre_sales_availability = "pre_sales_availability"
    pre_sales_pricing = "pre_sales_pricing"
    post_sales_checkin = "post_sales_checkin"
    special_request = "special_request"
    complaint = "complaint"
    general_enquiry = "general_enquiry"


class Action(str, Enum):
    """Routing decision attached to every drafted reply.

    auto_send    — confidence > 0.85, safe to send without human review.
    agent_review — confidence 0.60–0.85, needs a quick human check.
    escalate     — confidence < 0.60 or complaint, requires human handling.
    """

    auto_send = "auto_send"
    agent_review = "agent_review"
    escalate = "escalate"


# ---------------------------------------------------------------------------
# Request / Internal / Response schemas
# ---------------------------------------------------------------------------


class InboundMessage(BaseModel):
    """Raw payload received from the webhook. Matches the brief's input format."""

    source: MessageSource
    guest_name: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=4000)
    timestamp: datetime
    booking_ref: str | None = Field(default=None, max_length=80)
    property_id: str = Field(min_length=1, max_length=80)


class UnifiedMessage(BaseModel):
    """Channel-independent internal representation of a guest message.

    Every inbound payload is normalised into this schema before being
    passed to the AI drafter and confidence scorer.
    """

    message_id: UUID
    source: MessageSource
    guest_name: str
    message_text: str
    timestamp: datetime
    booking_ref: str | None
    property_id: str
    query_type: QueryType


class WebhookResponse(BaseModel):
    """Shape returned by POST /webhook/message."""

    message_id: UUID
    query_type: QueryType
    drafted_reply: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    action: Action
