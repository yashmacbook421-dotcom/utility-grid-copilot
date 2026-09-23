# Billing Adjustment Reason Codes

Illustrative implementation guidance — a generic pattern, not tied to any specific vendor's
product, menu path, or version.

## Why reason codes matter
Every billing adjustment or credit should be tagged with a structured reason code rather than
left as free text. Reason codes are what let a client later run a real report answering "how
much did we credit for meter-read estimation errors this quarter" instead of manually reading
every adjustment's notes field.

## A typical reason-code taxonomy
1. Meter-read correction — an estimated read replaced by an actual read.
2. Rate-plan retroactive correction — a customer was billed on the wrong plan for some period.
3. Service-quality credit — a credit tied to a documented outage or missed appointment.
4. Goodwill/courtesy adjustment — a one-off exception with no underlying billing error, usually
   capped by policy and requiring a supervisor approval code.
5. Tax or fee correction — a jurisdictional rate or fee was updated retroactively.

## What to confirm with the client before configuring
1. Which reason codes require a second approval before the adjustment posts, and what dollar
   threshold triggers that requirement.
2. Whether a reason code should automatically trigger a downstream action — for example, a
   service-quality credit that must also update an outage-tracking record.
3. Whether reason codes need to map to a general-ledger account for financial reporting; if so,
   that mapping should be confirmed with the client's finance team, not assumed by the
   implementation team.

## What not to do
Don't create an open-ended "other" reason code without a required free-text explanation —
without one, "other" tends to absorb the majority of adjustments within the first few months,
which defeats the reporting purpose the taxonomy exists for.
