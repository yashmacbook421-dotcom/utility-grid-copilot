"""Region registry.

"california" is the statewide CAISO aggregate; "smud" is the Sacramento
service area (BANC); "georgia" is the Southern Company footprint (SOCO) —
see app.services.eia_ingest for the respondent mapping and each region's
honesty caveat (BANC isn't SMUD-only, SOCO isn't Atlanta-only). All real
data, no synthetic generation. Kept as a dict (rather than a single
constant) because forecasting.py's per-region `has_temperature` flag is
still load-bearing: none of these regions has a live weather source wired
up yet, so temperature projection is skipped for all of them.
"""

REGION_PROFILES = {
    "california": {"has_temperature": False},
    "smud": {"has_temperature": False},
    "georgia": {"has_temperature": False},
}
