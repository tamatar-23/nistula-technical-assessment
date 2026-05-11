-- ============================================================================
-- Nistula unified messaging platform — PostgreSQL schema
-- Requires PostgreSQL 14+ for gen_random_uuid() support.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------

-- Every channel Nistula receives messages from.
CREATE TYPE message_source AS ENUM (
    'whatsapp',
    'booking_com',
    'airbnb',
    'instagram',
    'direct'
);

-- Classification categories for inbound guest messages.
CREATE TYPE query_type AS ENUM (
    'pre_sales_availability',
    'pre_sales_pricing',
    'post_sales_checkin',
    'special_request',
    'complaint',
    'general_enquiry'
);

CREATE TYPE message_direction AS ENUM ('inbound', 'outbound');

-- Tracks the lifecycle of a message through the AI → agent → send pipeline.
CREATE TYPE message_handling_status AS ENUM (
    'received',       -- just arrived, not yet processed
    'ai_drafted',     -- AI has generated a reply
    'agent_edited',   -- a human agent modified the AI draft
    'auto_sent',      -- sent automatically (confidence > 0.85)
    'sent',           -- sent after agent review
    'escalated',      -- routed to a human (complaint or low confidence)
    'failed'          -- delivery or processing failure
);

CREATE TYPE draft_action AS ENUM ('auto_send', 'agent_review', 'escalate');

-- ---------------------------------------------------------------------------
-- Core tables
-- ---------------------------------------------------------------------------

-- One row per real-world guest, regardless of how many channels they use.
-- A guest who messages via WhatsApp AND Airbnb still has one row here.
CREATE TABLE guests (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name  TEXT        NOT NULL,
    email      TEXT,
    phone      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Maps channel-specific identifiers to a single guest record.
-- This is what lets us say "WhatsApp user +91-xxx and Airbnb user abc123
-- are actually the same person."
CREATE TABLE guest_channel_identities (
    id                UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id          UUID           NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
    source            message_source NOT NULL,
    external_guest_id TEXT           NOT NULL,   -- e.g. phone number, Airbnb user ID
    display_name      TEXT,
    created_at        TIMESTAMPTZ    NOT NULL DEFAULT now(),

    UNIQUE (source, external_guest_id)
);

-- Properties managed by Nistula. Keeping a separate table so multiple villas,
-- apartments, etc. can each have their own context, rates, and metadata.
CREATE TABLE properties (
    id         TEXT        PRIMARY KEY,           -- e.g. "villa-b1"
    name       TEXT        NOT NULL,
    location   TEXT        NOT NULL,
    max_guests INTEGER     NOT NULL CHECK (max_guests > 0),
    metadata   JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A reservation ties a guest to a property for specific dates.
CREATE TABLE reservations (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_ref TEXT        NOT NULL UNIQUE,       -- e.g. "NIS-2024-0891"
    guest_id    UUID        NOT NULL REFERENCES guests(id),
    property_id TEXT        NOT NULL REFERENCES properties(id),
    check_in    DATE,
    check_out   DATE,
    guest_count INTEGER     CHECK (guest_count IS NULL OR guest_count > 0),
    status      TEXT        NOT NULL DEFAULT 'unknown',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Messaging tables
-- ---------------------------------------------------------------------------

-- A conversation groups messages between a guest and Nistula about a
-- specific property. reservation_id is nullable because pre-sales
-- conversations happen before any booking exists.
CREATE TABLE conversations (
    id              UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_id        UUID           NOT NULL REFERENCES guests(id),
    reservation_id  UUID           REFERENCES reservations(id),
    property_id     TEXT           NOT NULL REFERENCES properties(id),
    source          message_source NOT NULL,
    status          TEXT           NOT NULL DEFAULT 'open',
    last_message_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT now()
);

-- Every message — inbound and outbound, across all channels — lives here.
-- AI metadata (query_type, confidence) is stored directly on the message
-- row because support teams will filter and sort by these fields constantly.
CREATE TABLE messages (
    id                   UUID                   PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id      UUID                   NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    guest_id             UUID                   NOT NULL REFERENCES guests(id),
    reservation_id       UUID                   REFERENCES reservations(id),
    property_id          TEXT                   NOT NULL REFERENCES properties(id),
    source               message_source         NOT NULL,
    direction            message_direction      NOT NULL,
    external_message_id  TEXT,                                   -- channel's own message ID for dedup
    body                 TEXT                   NOT NULL,
    received_at          TIMESTAMPTZ,                            -- set for inbound
    sent_at              TIMESTAMPTZ,                            -- set for outbound
    query_type           query_type,                             -- classified on inbound messages only
    ai_confidence_score  NUMERIC(4, 3)          CHECK (ai_confidence_score IS NULL OR ai_confidence_score BETWEEN 0 AND 1),
    handling_status      message_handling_status NOT NULL DEFAULT 'received',
    created_at           TIMESTAMPTZ            NOT NULL DEFAULT now(),

    UNIQUE (source, external_message_id)
);

-- ---------------------------------------------------------------------------
-- AI draft tracking
-- ---------------------------------------------------------------------------

-- Stores every AI-generated draft for an inbound message. Separated from
-- messages because a single inbound message can produce multiple drafts
-- (retries, prompt revisions) and we want to keep the full history for
-- audits and model-quality analysis.
CREATE TABLE ai_drafts (
    id                  UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    inbound_message_id  UUID          NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    drafted_reply       TEXT          NOT NULL,
    model_name          TEXT          NOT NULL,
    confidence_score    NUMERIC(4, 3) NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
    recommended_action  draft_action  NOT NULL,
    was_auto_sent       BOOLEAN       NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- When an agent edits an AI draft before sending, the edit is recorded
-- here. This lets us measure how often and how much agents change AI output.
CREATE TABLE agent_message_edits (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id     UUID        NOT NULL REFERENCES ai_drafts(id) ON DELETE CASCADE,
    agent_id     UUID,                                           -- FK to an agents table in the full system
    edited_reply TEXT        NOT NULL,
    edit_reason  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Indexes for common query patterns
-- ---------------------------------------------------------------------------

CREATE INDEX idx_conversations_guest_id        ON conversations(guest_id);
CREATE INDEX idx_conversations_reservation_id  ON conversations(reservation_id);
CREATE INDEX idx_messages_conversation_created ON messages(conversation_id, created_at);
CREATE INDEX idx_messages_query_type           ON messages(query_type);
CREATE INDEX idx_messages_handling_status       ON messages(handling_status);
CREATE INDEX idx_ai_drafts_inbound_message_id  ON ai_drafts(inbound_message_id);

-- ============================================================================
-- Design decisions
-- ============================================================================
--
-- 1. Guests are channel-independent. A single guest who contacts Nistula via
--    WhatsApp and later via Airbnb still has one row in `guests`. The
--    `guest_channel_identities` table maps each channel-specific ID (phone
--    number, Airbnb user ID, etc.) back to that one guest record. This avoids
--    duplicate profiles and lets the support team see the full history.
--
-- 2. All messages live in one table regardless of channel or direction.
--    query_type and ai_confidence_score sit directly on the message row so
--    that support dashboards can filter and sort without joining. The full
--    AI draft text lives in a separate `ai_drafts` table (see point 4).
--
-- 3. Conversations link a guest to a property (and optionally a reservation).
--    reservation_id is nullable because pre-sales enquiries happen before any
--    booking exists. Once the guest books, the conversation can be linked.
--
-- 4. handling_status tracks the operational lifecycle: received → ai_drafted
--    → auto_sent / agent_edited → sent / escalated / failed. This gives ops
--    teams a clear picture of where every message is in the pipeline.
--
-- Hardest design decision
-- -----------------------
-- Whether to keep AI draft data on messages or in a separate table.
--
-- I went with a hybrid: query_type and confidence live on the message itself
-- because those are the fields the support team filters by constantly — every
-- dashboard query, every priority sort uses them. But the full drafted reply
-- text lives in `ai_drafts` as a separate table, because a single inbound
-- message can trigger multiple draft attempts (retries, prompt tweaks, or an
-- agent overriding the draft entirely). If I stored the draft inline on the
-- message row, each retry would overwrite the previous one, and we would lose
-- the audit trail needed for model-quality analysis and compliance reviews.
