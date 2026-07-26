# Peak Demand Response Procedure

## Trigger conditions
Initiate this procedure when the forecast median demand for any region exceeds 90% of that region's
firm capacity, or when the forecast upper bound exceeds 100% of firm capacity for two or more
consecutive hours.

## Step 1: Confirm the forecast
Cross-check the model's forecast peak against the prior 7-day same-weekday actuals. If the forecast
peak deviates from the seasonal baseline by more than 15%, flag it for manual review before dispatching
any load-shedding or demand-response signal — a large deviation is more often a data or weather-input
issue than a genuine new peak.

## Step 2: Activate demand response tiers
1. **Tier 1 (soft):** Send price signals / dynamic pricing notifications to enrolled commercial and
   residential customers 2 hours ahead of the forecast peak.
2. **Tier 2 (moderate):** Curtail enrolled industrial interruptible-load contracts 60-90 minutes ahead
   of peak. Confirm curtailment acknowledgement from each site before counting it toward relieved load.
3. **Tier 3 (hard):** Only if Tier 1 and Tier 2 combined relief is forecast to leave the region above
   98% of firm capacity, prepare rolling voltage reduction (conservation voltage reduction, up to 3%)
   as the next lever before considering rotating outages.

## Step 3: Coordinate with adjacent regions
Check whether neighboring regions have forecast headroom. Inter-region transfer capacity should be
requested at least 90 minutes before the forecast peak, since scheduling desks need lead time to
approve transfers.

## Step 4: Post-event review
Log the actual peak vs. forecast peak, which tiers were activated, and total MW relieved by each tier.
This feeds back into forecast model evaluation.
