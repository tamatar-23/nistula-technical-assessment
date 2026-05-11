"""Rule-based query classifier for guest messages.

Each inbound message is assigned one of six ``QueryType`` categories.
The classifier counts keyword hits per category and picks the category
with the most hits.  If nothing matches, the message falls through to
``general_enquiry``.

Complaint keywords are intentionally broad so that genuine guest
dissatisfaction is never silently auto-sent.  In production, a trained
model or Claude-based classification pass would replace this once enough
labelled data exists.
"""

from app.models import QueryType

# ---------------------------------------------------------------------------
# Keyword table — order here does NOT affect priority; only hit count does.
# ---------------------------------------------------------------------------

KEYWORDS: list[tuple[QueryType, tuple[str, ...]]] = [
    (
        QueryType.complaint,
        (
            "not working",
            "unacceptable",
            "refund",
            "angry",
            "unhappy",
            "not happy",
            "complaint",
            "broken",
            "dirty",
            "no hot water",
            "the ac",          # "the ac" avoids false matches inside words
            "ac is",           # like "accommodation" or "vacancy"
            "ac not",
        ),
    ),
    (
        QueryType.post_sales_checkin,
        (
            "check in",
            "check-in",
            "checkout",
            "check out",
            "wifi",
            "password",
            "arrival",
            "keys",
            "caretaker",
        ),
    ),
    (
        QueryType.special_request,
        (
            "early check",
            "late checkout",
            "airport",
            "transfer",
            "chef",
            "decor",
            "birthday",
            "anniversary",
            "special request",
        ),
    ),
    (
        QueryType.pre_sales_availability,
        (
            "available",
            "availability",
            "vacant",
            "dates",
            "book",
            "reserve",
        ),
    ),
    (
        QueryType.pre_sales_pricing,
        (
            "rate",
            "price",
            "cost",
            "tariff",
            "charges",
            "how much",
            "per night",
        ),
    ),
]


def classify_query(message_text: str) -> QueryType:
    """Return the best-matching ``QueryType`` for a guest message.

    Algorithm:
    1. Lowercase the message text.
    2. For each category, count how many of its keywords appear.
    3. Return the category with the highest hit count.
    4. If no keywords match at all, default to ``general_enquiry``.
    """
    text = message_text.lower()
    scores: dict[QueryType, int] = {}

    for query_type, keywords in KEYWORDS:
        scores[query_type] = sum(1 for kw in keywords if kw in text)

    best_type = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[best_type] > 0:
        return best_type

    return QueryType.general_enquiry
