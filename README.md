# Nistula Technical Assessment

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Sonnet_4-D97757?logo=anthropic&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-16_passed-brightgreen?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/License-Assessment-lightgrey)

Backend service that receives guest messages from multiple channels, normalises them into a unified schema, drafts AI replies via the Claude API, and returns each reply with a confidence score and routing action.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Framework | FastAPI |
| AI | Anthropic Claude Messages API (`claude-sonnet-4-20250514`) |
| HTTP client | httpx (async) |
| Config | pydantic-settings + `.env` |
| Tests | pytest + FastAPI TestClient |

## Repository Contents

```
app/
  __init__.py            Package marker
  main.py                FastAPI routes and application entry point
  models.py              Pydantic models: request, unified schema, response
  normalizer.py          Converts inbound payloads → unified messages
  classifier.py          Rule-based query classification (6 categories)
  claude_client.py       Claude API prompt builder and HTTP client
  confidence.py          Deterministic confidence scoring and action routing
  config.py              Environment-driven settings (API key, model, mock toggle)
  property_context.py    Mock Villa B1 context injected into prompts
tests/
  test_webhook.py        16 integration tests (mock mode, no API key needed)
schema.sql               Part 2 — PostgreSQL schema with design comments
thinking.md              Part 3 — Written answers to the 3am scenario
test_results.txt         Pytest output + live Claude API test results
.env.example             Template for required environment variables
requirements.txt         Python dependencies
```

---

## Setup & Run

### 1. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
copy .env.example .env      # Windows
cp .env.example .env         # macOS / Linux
```

Open `.env` and paste the assessment API key:

```env
ANTHROPIC_API_KEY=sk-ant-api03-...your-key-here...
ANTHROPIC_MODEL=claude-sonnet-4-20250514
USE_MOCK_CLAUDE=false
```

> To test the full pipeline **without** an API key, set `USE_MOCK_CLAUDE=true`.
> Mock mode returns hardcoded replies that mirror the real model's output for each query type.

### 4. Start the server

```bash
uvicorn app.main:app --reload
```

### 5. Verify it's running

```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok"}
```

### 6. Send a test message

```bash
curl -X POST http://127.0.0.1:8000/webhook/message \
  -H "Content-Type: application/json" \
  -d '{
    "source": "whatsapp",
    "guest_name": "Rahul Sharma",
    "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
    "timestamp": "2026-05-05T10:30:00Z",
    "booking_ref": "NIS-2024-0891",
    "property_id": "villa-b1"
  }'
```

Expected response:

```json
{
  "message_id": "9a4038f2-614a-4a35-9214-4e011ad75df9",
  "query_type": "pre_sales_availability",
  "drafted_reply": "Hi Rahul! Great news - Villa B1 in Assagao is available from April 20-24...",
  "confidence_score": 0.93,
  "action": "auto_send"
}
```

---

## Run Tests

```bash
pytest -v
```

The test suite has **16 tests** across five categories:

### Query classification (6 tests)

Every query type from the brief is covered with a dedicated test:

| Test | Input | Expected |
|---|---|---|
| `test_availability_query_auto_sends` | "Is the villa available from April 20 to 24?" | `pre_sales_availability`, auto-sent |
| `test_pricing_query_is_classified` | "How much does the villa cost per night for 5 guests?" | `pre_sales_pricing` |
| `test_checkin_query_is_classified` | "What time can we check in and what is the WiFi password?" | `post_sales_checkin`, reply contains "2pm" |
| `test_special_request_is_classified` | "Can we arrange a chef for dinner? Also need an airport transfer." | `special_request` |
| `test_complaint_is_escalated` | "The AC is not working. I am not happy and want a refund." | `complaint`, confidence < 0.60, escalated |
| `test_general_enquiry_fallback` | "Do you allow pets at the villa?" | `general_enquiry` |

### Confidence & action routing (2 tests)

| Test | What it verifies |
|---|---|
| `test_high_confidence_with_full_context` | Known property + booking ref + specific terms → confidence > 0.85, auto-sent |
| `test_lower_confidence_without_booking_ref` | Missing booking ref → confidence drops compared to full context |

### Response shape (2 tests)

| Test | What it verifies |
|---|---|
| `test_response_contains_all_required_fields` | All 5 brief-required fields present: `message_id`, `query_type`, `drafted_reply`, `confidence_score`, `action` |
| `test_message_id_is_valid_uuid` | `message_id` is a valid UUID v4 string |

### Input validation (4 tests)

| Test | What it verifies |
|---|---|
| `test_invalid_source_returns_422` | Unsupported channel (`sms`) → 422 |
| `test_empty_message_returns_422` | Empty message body → 422 |
| `test_missing_guest_name_returns_422` | Missing required field → 422 |
| `test_missing_property_id_returns_422` | Missing required field → 422 |

### Multi-channel & health (2 tests)

| Test | What it verifies |
|---|---|
| `test_all_valid_sources_are_accepted` | All 5 channels (`whatsapp`, `booking_com`, `airbnb`, `instagram`, `direct`) return 200 |
| `test_health_endpoint` | `GET /health` returns `{"status": "ok"}` |

### Live Claude API tests

In addition to the unit tests above, three end-to-end tests were run against the real Claude API. Full request/response pairs are recorded in [`test_results.txt`](test_results.txt).

| # | Input | Query Type | Confidence | Action |
|---|---|---|---|---|
| 1 | Availability + pricing (WhatsApp) | `pre_sales_availability` | 0.93 | `auto_send` |
| 2 | Check-in + WiFi (Booking.com) | `post_sales_checkin` | 0.97 | `auto_send` |
| 3 | 3am complaint + refund (WhatsApp) | `complaint` | 0.55 | `escalate` |

---

## How It Works

### Request Flow

```
POST /webhook/message
        │
        ▼
  ┌─────────────┐
  │  Normaliser  │  → Strips whitespace, generates UUID, maps to unified schema
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  Classifier  │  → Counts keyword hits per category, picks best match
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ Claude Client│  → Builds prompt with property context, calls API (or mock)
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  Confidence  │  → Deterministic score + action routing
  └──────┬──────┘
         │
         ▼
   WebhookResponse
```

### Query Classification

The classifier uses a keyword-counting approach: for each of the six query categories, it counts how many category-specific keywords appear in the message. The category with the most hits wins. If nothing matches, the message defaults to `general_enquiry`.

This means a mixed message like *"Is the villa available from April 20 to 24? What is the rate for 2 adults?"* gets classified as `pre_sales_availability` because it has more availability-related keyword hits than pricing hits.

Complaint keywords are intentionally broad so that guest dissatisfaction is never silently auto-sent. In production, a trained classifier or Claude-based classification pass would replace keyword matching once labelled data exists.

### Confidence Scoring

Confidence is **deterministic and explainable** — the model is never asked to grade itself.

| Factor | Effect |
|---|---|
| Base score | 0.68 |
| Known property (`villa-b1`) | +0.08 |
| Has booking reference | +0.04 |
| Draft is non-trivial (≥ 40 chars) | +0.05 |
| High-certainty keywords matched (per term, max 3) | +0.04 each (cap +0.12) |
| Urgent / refund / ambiguous language | −0.12 |
| Complaint (any) | Hard-capped at 0.55 |

**Action routing:**

| Confidence | Action |
|---|---|
| > 0.85 | `auto_send` — safe to send without human review |
| 0.60 – 0.85 | `agent_review` — needs a quick human check |
| < 0.60 *or* complaint | `escalate` — requires human handling |

Straightforward availability, rate, WiFi, and check-in replies can be auto-sent when the property context directly answers the question. Complaints and refund situations always escalate.

### Claude Prompting

The prompt sent to Claude includes:

- Reply-style instructions (warm, concise, operationally safe)
- The full Villa B1 property context from the brief
- All normalised message fields (guest name, source, booking ref, query type)
- A word-count constraint (under 120 words)

Temperature is set to `0.2` to keep replies consistent and operationally safe.

---

## Error Handling

| Scenario | HTTP Status | Detail |
|---|---|---|
| Invalid or missing payload fields | `422` | FastAPI validation error with field-level messages |
| Claude API HTTP error | `502` | `"Claude API returned {status_code}"` |
| Claude API unreachable | `502` | `"Could not reach Claude API"` |
| Missing API key (mock mode off) | `502` | `"ANTHROPIC_API_KEY is not configured..."` |
| Empty Claude response | `502` | `"Claude API response did not include reply text"` |

---

## Design Decisions

1. **Rule-based classification** — transparent and easy to review. Every classification can be traced back to the keyword that triggered it.
2. **Claude is isolated** behind `claude_client.py`, so it can be mocked in tests and swapped for another provider without touching the rest of the pipeline.
3. **Confidence is deterministic** — calculated from message metadata and keyword matches, not from the model's self-assessment. This makes scores reproducible and auditable.
4. **Raw `httpx` instead of the Anthropic SDK** — keeps the dependency footprint minimal and makes the API interaction fully visible in one file.
5. **Mock mode** — `USE_MOCK_CLAUDE=true` lets the full pipeline run end-to-end without an API key, useful for testing, CI, and code review.
