
-- Seed synthetic demand data for 3 regions, 90 days hourly
INSERT INTO demand_readings (time, region, demand_mw, temperature_c, solar_generation_mw, ev_load_mw, is_holiday)
SELECT
  ts,
  region,
  round(base_demand * seasonal * daily * weekend * noise) AS demand_mw,
  round((15 + 10 * sin(2 * pi() * (extract(month from ts) - 5) / 12) + 5 * sin(2 * pi() * extract(hour from ts) / 24))::numeric, 2) AS temperature_c,
  0, 0,
  (extract(month from ts) = 12 AND extract(day from ts) IN (25, 26)) AS is_holiday
FROM (
  SELECT
    generate_series(
      date_trunc('hour', now() - interval '90 days')::timestamptz,
      date_trunc('hour', now())::timestamptz,
      interval '1 hour'
    ) AS ts
) times
CROSS JOIN (
  SELECT 'california' AS region, 28000 AS base_demand
  UNION ALL SELECT 'smud', 3000
  UNION ALL SELECT 'georgia', 11000
) regions,
LATERAL (
  SELECT
    1 + 0.3 * sin(2 * pi() * (extract(month from ts) - 5) / 12) AS seasonal,
    1 + 0.25 * sin(2 * pi() * (extract(hour from ts) - 6) / 24) AS daily,
    CASE WHEN extract(dow from ts) IN (0, 6) THEN 0.85 ELSE 1.0 END AS weekend,
    0.95 + random() * 0.1 AS noise
) factors
ON CONFLICT (time, region) DO NOTHING;
