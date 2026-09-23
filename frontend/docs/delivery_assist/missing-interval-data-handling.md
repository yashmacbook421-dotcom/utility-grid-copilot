# Missing Interval Data Handling

Illustrative implementation guidance — a generic pattern, not tied to any specific vendor's
product, menu path, or version.

## Why gaps happen
Interval meters (typically 15-minute or hourly) can drop individual intervals due to a
communication outage, a meter reboot, or a network gateway issue, without the meter itself being
faulty. A short gap is routine and expected at scale; a systemic gap across many meters usually
indicates a network-side problem rather than individual meter failures.

## Filling a gap
A single short gap (a handful of missing intervals) is typically filled by interpolating between
the surrounding good intervals, or by substituting the same time-of-day pattern from a nearby
day with similar characteristics (same day-of-week, similar weather). A longer or repeated gap
on the same meter is a signal to route it to the exception queue described in the usage
validation pattern, rather than keep auto-filling it — repeated silent substitution can mask a
genuinely failing meter.

## What to confirm with the client before configuring
1. The gap-length threshold above which auto-fill stops and a human review is required.
2. Whether a substituted interval is visibly flagged as estimated in downstream billing and
   customer-facing usage displays, or only in internal records.
3. How a billing determinant calculated from data containing filled intervals (e.g. a monthly
   peak demand charge) should be flagged if a meaningful share of the period was estimated.

## What not to do
Don't apply the same gap-filling method to a residential load profile and a large commercial
account with irregular, shift-driven usage patterns — interpolation and day-matching both
assume some regularity that a genuinely irregular account may not have.
