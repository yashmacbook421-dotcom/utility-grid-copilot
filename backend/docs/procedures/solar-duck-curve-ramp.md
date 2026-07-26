# Solar Duck-Curve Evening Ramp

## The problem
As midday solar generation grows, net demand (demand minus solar) drops sharply in the afternoon and
then ramps steeply upward in the 2-3 hours after sunset as solar falls to zero while residential and
EV demand rise. This is the "duck curve." Ramp rates above 25 MW/15-min block are considered high-risk
for regions without fast-start peaking capacity.

## Forecasting checklist
- Compare the forecast net-demand ramp rate (MW per 15-minute interval) between 17:00 and 20:00 against
  the region's fast-start generation capacity. If forecast ramp exceeds 80% of available fast-start
  capacity, flag for pre-positioning.
- Cloud cover forecasts materially affect solar drop-off timing; if cloud cover forecast confidence is
  low, widen the operational buffer by starting fast-start unit warm-up 30 minutes earlier than the
  model's median ramp-start estimate.

## Mitigation levers, in order of preference
1. Dispatch battery storage to discharge starting 30-45 minutes before the forecast ramp begins,
   targeting a flatter net-demand slope rather than waiting for the ramp to start.
2. Begin fast-start (gas peaker) unit warm-up sequences at T-45 minutes before forecast ramp start.
3. Coordinate with EV Charging Load Management procedure to shift managed EV load later into the
   evening, reducing the steepness of the ramp's leading edge.
4. If ramp risk remains high after 1-3, request inter-region import capacity per the Peak Demand
   Response procedure, Step 3.
