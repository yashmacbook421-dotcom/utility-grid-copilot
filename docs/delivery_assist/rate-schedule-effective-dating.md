# Rate Schedule Effective-Dating and Mid-Cycle Changes

Illustrative implementation guidance — a generic pattern, not tied to any specific vendor's
product, menu path, or version.

## The core pattern
A rate schedule change is modeled with effective dates, not by editing a schedule in place: the
old schedule's effective-to date is set to the day before the change, and the new schedule's
effective-from date starts the change. The billing process then splits any bill period that
spans the change date into two segments, each calculated under its own applicable schedule and
combined onto a single bill.

## Splitting the billing period
The segment split can be driven three different ways, and the choice has real billing-accuracy
implications:
1. An actual interval or mid-cycle read taken at the change date — most accurate, requires
   either interval metering or a special read.
2. A straight-line proration of the single end-of-cycle read, splitting usage proportionally by
   the number of days in each segment — simplest, least accurate for customers with uneven
   usage across the period.
3. An estimated read at the change date based on historical usage pattern — a middle ground.

## What to confirm with the client before configuring
1. Which of the three splitting methods applies, and whether it can vary by rate schedule or
   customer class.
2. How time-of-use tiers or demand charges that reset per billing period interact with a
   mid-cycle split — a demand charge based on a monthly peak needs a defined rule for which
   segment's peak counts, or whether each segment gets its own independent peak.
3. Whether the change should be customer-initiated (self-service plan switch) or only
   utility-initiated (a rate case decision affecting all customers on a schedule) — the two
   have different approval and notification requirements.

## What not to do
Don't assume straight-line proration is "good enough" without confirming it with the client for
rate schedules where usage is materially uneven across a period (e.g. seasonal agricultural or
EV-heavy commercial accounts) — it produces bills customers can reasonably dispute.
