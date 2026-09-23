# Work Order Prioritization Basics

Illustrative implementation guidance — a generic pattern, not tied to any specific vendor's
product, menu path, or version. Scope note: this document covers general work-order priority
and scheduling concepts only. It does not cover crew shift patterns, union work rules, or
emergency-dispatch staffing models — those vary too much by client to generalize, and should be
scoped directly with the client's operations team rather than answered from a generic pattern.

## Priority tiers
Work orders are typically bucketed into a small number of priority tiers rather than a
continuous score: emergency (immediate safety or reliability risk), urgent (same-day or
next-day), routine (scheduled maintenance), and planned (part of a longer capital or
preventive-maintenance program). Emergency work generally preempts everything else in the
scheduling queue.

## Preventive vs. corrective work
Preventive work is scheduled on a fixed interval or condition-based trigger (an inspection
finding) before a failure occurs. Corrective work is created in response to an already-occurred
failure or fault report. A healthy work-management program tracks the ratio between the two over
time — a rising share of corrective work relative to preventive is usually an early signal that
preventive intervals are too infrequent or maintenance is falling behind.

## What to confirm with the client before configuring
1. The exact tier definitions and their target response-time windows — these differ by
   regulatory jurisdiction and by asset class (a downed line and a minor equipment fault are
   both "urgent" in casual language but usually belong in different tiers).
2. Whether priority can escalate automatically over time (an unresolved routine order becomes
   urgent after N days) or only through manual reassignment.
3. How planned capital work and reactive corrective work share the same crew capacity — most
   disputes in this area come from planned work being silently deprioritized without a visible
   tradeoff decision.

## What not to do
Don't answer a crew-scheduling, shift-pattern, or union-rule question from this document — it
doesn't cover that scope. Route those questions to a subject-matter expert with work-management
delivery experience for the specific client.
