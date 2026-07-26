# EV Charging Load Management

## Why this matters
Uncoordinated EV charging concentrates load between 18:00 and 22:00, directly stacking on top of the
traditional evening residential peak. In regions with EV load capacity above 300 MW, this can shift
the daily peak later and make it sharper than the historical daily shape would suggest.

## Managed charging signals
When forecast EV load contribution to the evening peak exceeds 20% of total forecast demand:
1. Push a "shift to off-peak" notification to customers enrolled in the managed-charging program,
   recommending charging after 23:00 or using scheduled/smart-charging mode.
2. For fleet and depot charging contracts, apply the contracted managed-charging curtailment schedule
   — these contracts have priority scheduling rights but are capped at 2 curtailment events per week.
3. Do not curtail residential Level 1/Level 2 home charging involuntarily; only managed/enrolled load
   is eligible for automatic curtailment signals.

## Interaction with solar ramp
EV charging demand response is most valuable in the 17:00-20:00 window, which overlaps with the solar
ramp-down. Coordinating EV curtailment with battery storage discharge (see Storm & Ramp procedures)
can flatten the ramp more effectively than either lever alone.

## Escalation
If managed charging signals are insufficient to bring the region under 95% of firm capacity by T-60
minutes, escalate to the Peak Demand Response procedure, Tier 2.
