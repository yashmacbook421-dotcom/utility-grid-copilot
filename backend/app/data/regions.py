"""Region registry.

"california" is the statewide CAISO aggregate; "smud" is the Sacramento
service area (BANC); "georgia" is the Southern Company footprint (SOCO) —
see app.services.eia_ingest for the respondent mapping and each region's
honesty caveat (BANC isn't SMUD-only, SOCO isn't Atlanta-only). All real
data, no synthetic generation. Kept as a dict (rather than a single
constant) because forecasting.py's per-region `has_temperature` flag is
still load-bearing: it's what tells forecast() whether to call
app.services.weather_ingest for a real forecasted temperature, or skip the
feature (NaN) for a region with no weather source configured.
"""

REGION_PROFILES = {
    "california": {"has_temperature": True},
    "smud": {"has_temperature": True},
    "georgia": {"has_temperature": True},
}
