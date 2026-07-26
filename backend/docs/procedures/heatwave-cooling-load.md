# Heatwave Cooling Load Procedure

## Trigger
Forecast temperature above 32C sustained for 3+ consecutive hours in any region, or a forecast
temperature that is more than 8C above the seasonal mean for that day of year.

## Expected load behavior
Cooling load (air conditioning) scales roughly linearly above a ~24C comfort threshold. During
sustained heatwaves, actual demand frequently exceeds the model's forecast upper bound because
cooling load compounds: buildings that failed to fully cool overnight draw more AC load the next
afternoon than the same daytime temperature would suggest in isolation. Treat the model's forecast
upper bound as a floor, not a ceiling, on days 2+ of a multi-day heatwave.

## Actions
1. On day 1 of a forecast heatwave, pre-notify large commercial/industrial customers of possible
   Tier 1 demand response signals for days 2-3, giving them time to pre-cool facilities overnight
   (shifting some cooling load to off-peak hours ahead of the heat).
2. Increase reserve margin targets by 5% above standard operating reserve for the duration of the
   heatwave.
3. Monitor distribution transformer loading in high-density residential areas; sustained heat
   increases transformer failure risk independent of total system headroom.
4. If actual demand exceeds forecast upper bound by more than 5% in real time, immediately escalate
   to Peak Demand Response Tier 2, do not wait for the next forecast refresh cycle.
