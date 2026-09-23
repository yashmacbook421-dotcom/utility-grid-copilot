DO $do$
DECLARE
  doc_id uuid;
BEGIN
  INSERT INTO documents (title, organization, document_type, source_url)
  VALUES ('Peak Demand Response', 'synthetic', 'internal_procedure', 'peak-demand-response.md')
  RETURNING id INTO doc_id;

  INSERT INTO document_chunks (document_id, chunk_index, content, embedding)
  VALUES (doc_id, 0, '# Peak Demand Response Procedure

## Trigger conditions
Initiate this procedure when the forecast median demand for any region exceeds 90% of that region''s
firm capacity, or when the forecast upper bound exceeds 100% of firm capacity for two or more
consecutive hours.

## Step 1: Confirm the forecast
Cross-check the model''s forecast peak against the prior 7-day same-weekday actuals. If the forecast
peak deviates from the seasonal baseline by more than 15%, flag it for manual review before dispatching
any load-shedding or demand-response signal — a large deviation is more often a data or weather-input
issue than a genuine new peak.

## Step 2: Activate demand response tiers
1. **Tier 1 (soft):** Send price signals / dynamic pricing notifications to enrolled commercial and
   residential customers 2 hours ahead of the forecast peak.
2. **Tier 2 (moderate):** Curtail enrolled industrial interruptible-load contracts 60-90 minutes ahead
   of peak. Confirm curtailment acknowledgement from each site before counting it toward relieved load.
3. **Tier 3 (hard):** Only if Tier 1 and Tier 2 combined relief is forecast to leave the region above
   98% of firm capacity, prepare rolling voltage reduction (conservation voltage reduction, up to 3%)', hash_embed_384('# Peak Demand Response Procedure

## Trigger conditions
Initiate this procedure when the forecast median demand for any region exceeds 90% of that region''s
firm capacity, or when the forecast upper bound exceeds 100% of firm capacity for two or more
consecutive hours.

## Step 1: Confirm the forecast
Cross-check the model''s forecast peak against the prior 7-day same-weekday actuals. If the forecast
peak deviates from the seasonal baseline by more than 15%, flag it for manual review before dispatching
any load-shedding or demand-response signal — a large deviation is more often a data or weather-input
issue than a genuine new peak.

## Step 2: Activate demand response tiers
1. **Tier 1 (soft):** Send price signals / dynamic pricing notifications to enrolled commercial and
   residential customers 2 hours ahead of the forecast peak.
2. **Tier 2 (moderate):** Curtail enrolled industrial interruptible-load contracts 60-90 minutes ahead
   of peak. Confirm curtailment acknowledgement from each site before counting it toward relieved load.
3. **Tier 3 (hard):** Only if Tier 1 and Tier 2 combined relief is forecast to leave the region above
   98% of firm capacity, prepare rolling voltage reduction (conservation voltage reduction, up to 3%)'));

  INSERT INTO document_chunks (document_id, chunk_index, content, embedding)
  VALUES (doc_id, 1, '98% of firm capacity, prepare rolling voltage reduction (conservation voltage reduction, up to 3%)
   and notify the reliability coordinator. Do not execute Tier 3 without explicit verbal authorization
   from the on-shift chief operator.

## Step 3: Notify
1. Notify the reliability coordinator (NERC EOP-011-4) of any Tier 2 or Tier 3 activation within 15
   minutes of execution.
2. Log the event in the operations log with timestamp, tier activated, estimated load relief, and
   authorizing operator name.

## Post-event
After the peak has passed and demand has returned below 85% of firm capacity:
1. De-activate demand response signals in reverse tier order (Tier 3 first, then 2, then 1).
2. Within 24 hours, review actual vs. forecast demand to calibrate future forecasts — if actual peak
   exceeded the forecast upper bound, flag the model for retraining on this event.
3. Within 48 hours, file a post-event report with the regulatory team if any Tier 3 action was taken.', hash_embed_384('98% of firm capacity, prepare rolling voltage reduction (conservation voltage reduction, up to 3%)
   and notify the reliability coordinator. Do not execute Tier 3 without explicit verbal authorization
   from the on-shift chief operator.

## Step 3: Notify
1. Notify the reliability coordinator (NERC EOP-011-4) of any Tier 2 or Tier 3 activation within 15
   minutes of execution.
2. Log the event in the operations log with timestamp, tier activated, estimated load relief, and
   authorizing operator name.

## Post-event
After the peak has passed and demand has returned below 85% of firm capacity:
1. De-activate demand response signals in reverse tier order (Tier 3 first, then 2, then 1).
2. Within 24 hours, review actual vs. forecast demand to calibrate future forecasts — if actual peak
   exceeded the forecast upper bound, flag the model for retraining on this event.
3. Within 48 hours, file a post-event report with the regulatory team if any Tier 3 action was taken.'));
END $do$;