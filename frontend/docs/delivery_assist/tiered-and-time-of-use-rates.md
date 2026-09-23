# Tiered and Time-of-Use Rate Structure Basics

Illustrative implementation guidance — a generic pattern, not tied to any specific vendor's
product, menu path, or version.

## Tiered rates
A tiered rate charges a different per-kWh price depending on how much a customer has used
within the billing period — usage in the first block (e.g. 0-500 kWh) is priced lower than usage
above it. Tiers reset every billing period and are usually justified as an incentive for
conservation.

## Time-of-use (TOU) rates
A TOU rate instead prices usage by *when* it happens — on-peak, off-peak, and sometimes
mid-peak windows, each with its own price, reflecting the utility's real cost of serving load at
that time of day. TOU requires interval metering (typically 15-minute or hourly intervals); a
customer without interval-capable metering cannot be validly billed on a TOU schedule.

## Combining the two
Some rate designs combine both — tiered pricing within each TOU period. This is more complex to
configure and to explain to customers, and materially increases the number of edge cases in
billing determinant calculation (e.g. which tier does a given interval's usage count against,
and does the tier reset per TOU period or per full day).

## What to confirm with the client before configuring
1. Which customer segments are eligible for which structure, and whether enrollment is
   opt-in, opt-out, or mandatory for new construction.
2. The exact peak/off-peak window definitions, including how holidays and weekends are treated
   — these are a frequent source of billing disputes if not documented precisely.
3. Whether a rate switch mid-cycle is allowed, and if so, how it interacts with the effective-
   dating pattern used for other rate changes.

## What not to do
Don't enable a TOU rate for a customer class without first confirming interval-metering
coverage for that class — offering a rate a meter can't actually support produces bills that
can't be defended if disputed.
