# Part 3 — 3am Hot Water Complaint

## Question A — The Immediate Response

> Hi, I'm so sorry you're dealing with this — especially with guests arriving in a few hours. I've flagged this as urgent and the on-call manager is being contacted right now to get someone over to fix the hot water as soon as possible. Your refund request has been noted and the manager will follow up with you on that once the situation is resolved. Please hang tight, someone will reach out to you shortly.

I went with this wording because the guest is frustrated and the worst thing the AI can do is sound robotic or defensive. The message leads with empathy, gives a concrete next step (on-call manager is being contacted), and doesn't make a refund promise the AI has no authority to make. It also doesn't over-apologise — the guest wants action, not five lines of "we're sorry."

## Question B — The System Design

The moment this message hits the platform, a few things should happen in parallel:

First, classify it as a complaint with an **emergency** priority tag — "no hot water" plus the time of day (3am) plus the tone ("unacceptable", "refund") all point to urgency. Create an incident record tied to the reservation and Villa B1, and immediately push notifications to the on-call operations manager, the villa caretaker, and a shared Slack/WhatsApp escalation channel. The AI-drafted reply gets sent to the guest, but the conversation is locked into agent-review mode so no further AI messages go out unsupervised.

Everything gets logged: the original message, the AI reply, the confidence score, the escalation reason, notification delivery timestamps, and whether each notified person acknowledged.

If nobody acknowledges within 30 minutes, the system should auto-escalate — notify the property head and a backup maintenance vendor, trigger a phone call to the operations manager (not just a push notification), and send the guest a follow-up saying something like "We've escalated this further and someone will call you shortly." At 3am, push notifications get missed. Phone calls don't.

## Question C — The Learning

Three hot water complaints at the same property in two months isn't a coincidence — it's a pattern, and the system should treat it as one. Right now these are probably sitting as three separate closed tickets that nobody has connected.

I'd build a simple recurring-issue detector: group resolved incidents by property + asset type + symptom, and when the count crosses a threshold (say, 2 in 60 days), flag it as a **reliability risk** on the property's dashboard. Villa B1's hot water system would show up as a known issue that needs a root-cause fix, not just another repair.

To actually prevent a fourth complaint, I'd require maintenance closure notes (what was the root cause? was the part replaced or just patched?), schedule a preventive plumbing check before every upcoming check-in at that villa, and add "verify hot water" to the pre-arrival checklist the caretaker runs through. On the agent side, when a new booking comes in for Villa B1, the system should surface a warning: "Hot water has been reported twice recently — confirm it's working before the guest arrives."

The goal is to catch the problem before the guest has to tell us about it.
