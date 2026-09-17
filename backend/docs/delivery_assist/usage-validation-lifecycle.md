# Meter Usage Validation, Estimation, and Exception Handling

Illustrative implementation guidance — a generic pattern, not tied to any specific vendor's
product, menu path, or version.

## The core pattern
Incoming meter readings are checked against tolerance rules before they're allowed to bill:
a reading that's a large spike or drop versus recent history, a zero read on a previously
active account, or a missing interval are all common tolerance-rule triggers. A reading that
fails validation is not silently billed and not silently discarded — it's routed into an
exception queue for review, while the account either waits or receives an estimated read for
that period, depending on client policy.

## Estimation
When a real read is unavailable or fails validation, a reasonable estimate — typically based on
the account's own recent historical usage adjusted for weather or season — stands in until a
verified read arrives. Estimation should be visibly flagged on the bill and automatically
corrected (a "true-up") once the next real read is available, rather than silently absorbed.

## Setting tolerance thresholds
Tolerance thresholds involve a real tradeoff: too strict, and the exception queue floods with
false positives (a legitimately high-usage day during a heatwave gets flagged unnecessarily);
too loose, and genuinely bad reads (a stuck or misread meter) bill without review. Thresholds
are usually tuned per customer class, since a large commercial account's normal usage variance
is very different from a residential account's.

## What to confirm with the client before configuring
1. Which exception categories can be auto-resolved by a rule (e.g. auto-accept a read within a
   slightly wider tolerance if the account has no prior exceptions) versus which always require
   a human decision.
2. The true-up policy once a corrected read arrives — how many prior estimated periods get
   retroactively adjusted.
3. Escalation ownership: who reviews the exception queue, and what the target turnaround time is
   before an unresolved exception blocks a bill run.

## What not to do
Don't set a single global tolerance threshold across every customer class — a threshold tuned
for residential accounts will either flood the queue with commercial false positives or miss
genuine commercial anomalies, depending on which direction it's set.
