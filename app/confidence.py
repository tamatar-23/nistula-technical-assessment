"""Deterministic confidence scoring and action routing.

Confidence is calculated with transparent, rule-based adjustments rather
than asking the model to self-grade.  Every factor is a simple add or
subtract from a base score, making the result fully explainable and
auditable.

Score ranges and their corresponding actions:
    > 0.85  → auto_send     (safe to send without human review)
    0.60–0.85 → agent_review (needs a quick human check)
    < 0.60  → escalate      (requires human handling)
    complaint → always escalate regardless of score
"""

from app.models import Action, QueryType, UnifiedMessage

# Terms that, when present in the message AND matching the classified
# query type, indicate the guest is asking something the property context
# can directly answer — increasing confidence in the draft.
HIGH_CERTAINTY_TERMS: dict[QueryType, tuple[str, ...]] = {
    QueryType.pre_sales_availability: ("april 20", "april 24", "available", "availability"),
    QueryType.pre_sales_pricing: ("rate", "price", "2 adults", "per night"),
    QueryType.post_sales_checkin: ("check-in", "check in", "wifi", "password"),
    QueryType.special_request: ("airport", "transfer", "chef", "early"),
    QueryType.general_enquiry: ("parking", "pets", "pool", "bedrooms", "guests"),
}


def calculate_confidence(message: UnifiedMessage, drafted_reply: str) -> float:
    """Return a confidence score between 0.0 and 1.0.

    Scoring breakdown:
    - Complaints are hard-capped at 0.55 (always escalated).
    - Base score: 0.68
    - Known property (villa-b1): +0.08
    - Has booking reference:     +0.04
    - Draft is non-trivial:      +0.05
    - Each high-certainty term:  +0.04 (max +0.12)
    - Urgent / refund language:  −0.12
    """
    # Complaints are always escalated — cap below the agent_review threshold.
    if message.query_type == QueryType.complaint:
        return 0.55

    score = 0.68
    text = message.message_text.lower()

    # Property context is hardcoded for villa-b1; known context = higher trust.
    if message.property_id == "villa-b1":
        score += 0.08

    # A booking reference ties the message to a real reservation.
    if message.booking_ref:
        score += 0.04

    # A reasonably long draft means the model produced a substantive reply.
    if len(drafted_reply.strip()) >= 40:
        score += 0.05

    # If the guest's message contains terms the property context can directly
    # answer for this query type, the draft is more likely to be correct.
    matched_terms = sum(
        1 for term in HIGH_CERTAINTY_TERMS.get(message.query_type, ()) if term in text
    )
    score += min(matched_terms * 0.04, 0.12)

    # Urgent, ambiguous, or refund language reduces confidence because
    # these messages need human judgement even if the draft looks correct.
    if any(word in text for word in ("maybe", "urgent", "asap", "refund", "unacceptable")):
        score -= 0.12

    return round(min(max(score, 0.0), 0.98), 2)


def choose_action(query_type: QueryType, confidence_score: float) -> Action:
    """Map query type and confidence score to a routing action."""
    if query_type == QueryType.complaint or confidence_score < 0.60:
        return Action.escalate
    if confidence_score > 0.85:
        return Action.auto_send
    return Action.agent_review
