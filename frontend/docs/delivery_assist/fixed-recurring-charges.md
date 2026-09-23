# Fixed Recurring Charge Patterns

Illustrative implementation guidance — a generic pattern, not tied to any specific vendor's
product, menu path, or version.

## The core pattern
A fixed monthly service charge (sometimes called a customer charge or basic service fee) is
modeled as a flat amount applied once per billing period, independent of metered consumption.
It is kept as a separate charge component from usage-based charges rather than blended into a
per-kWh rate, for two reasons: it must still bill on a zero-usage account, and it must be
individually visible on the bill and in any rate-change audit trail.

## Proration
When the billing period is shorter than a full cycle — a new account mid-period, a rate-plan
switch mid-cycle, a final bill at service disconnection — the fixed charge is typically prorated
by the number of days actually served divided by the standard cycle length, not billed in full
or waived entirely. Decide and document the proration day-count convention (calendar days vs.
billing days) once per implementation; inconsistent proration between similar scenarios is a
common source of billing disputes.

## What to confirm with the client before configuring
1. Whether the fixed charge varies by customer class (residential vs. commercial) or service
   type (electric vs. gas) — this determines whether it belongs on the base rate schedule or a
   separate rider.
2. Whether multiple fixed charges can stack (e.g. a base customer charge plus a separate meter
   charge) or must be mutually exclusive.
3. The exact proration convention, confirmed in writing, before the first billing cycle runs —
   not discovered from a customer complaint after go-live.

## What not to do
Don't assume a single "standard" proration method applies across all client implementations —
this varies enough between utilities that copying a prior client's configuration without
confirming it with the current client is a real source of go-live billing errors.
