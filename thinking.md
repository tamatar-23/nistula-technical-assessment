# Part 3 — 3am Hot Water Complaint

## Question A — The Immediate Response

> Hi, I'm so sorry you're dealing with this — especially with guests arriving in a few hours. I've flagged this as urgent and the on-call manager is being contacted right now to get the hot water fixed. Your refund request has been noted and the manager will follow up once the situation is resolved. Someone will reach out to you shortly.

I went with this wording because the guest wants action, not apologies. It leads with empathy, gives a concrete next step, and doesn't promise a refund the AI has no authority to approve.

## Question B — The System Design

The moment this message arrives, classify it as a complaint with emergency priority — "no hot water" plus the tone plus the time of day all point to urgency. Create an incident tied to the reservation and Villa B1. Push notifications to the on-call ops manager, caretaker, and a shared escalation channel. The AI reply goes to the guest, but the conversation locks into agent-review mode so no further AI messages go out unsupervised.

Log everything: the message, AI reply, confidence score, escalation reason, and whether each person acknowledged. If nobody responds within 30 minutes, auto-escalate — notify the property head, trigger a phone call to the ops manager, and send the guest a follow-up saying someone will call them shortly. At 3am, push notifications get missed. Phone calls don't.

## Question C — The Learning

Three hot water complaints at the same property in two months is a pattern, not a coincidence. I'd build a recurring-issue detector that groups incidents by property and symptom, and flags Villa B1 hot water as a reliability risk once it crosses a threshold.

To prevent a fourth complaint: require root-cause notes before closing maintenance tickets, schedule a preventive plumbing check before every upcoming check-in, and add "verify hot water" to the caretaker's pre-arrival checklist. When a new booking comes in for Villa B1, the system should warn agents that hot water has recent complaint history so they can confirm it's working before the guest arrives.
