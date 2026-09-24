import { getSupabaseServer } from "./supabase-server";
import { REGION_COORDS, REGION_PROFILES } from "./regions";
import { cacheGet, cacheSet, makeKey } from "./cache";

export interface DemandPoint {
  time: string;
  demand_mw: number;
  temperature_c?: number | null;
  solar_generation_mw?: number;
  ev_load_mw?: number;
}

export interface ForecastPoint {
  time: string;
  predicted_demand_mw: number;
  lower_bound_mw: number;
  upper_bound_mw: number;
}

export interface ForecastData {
  region: string;
  generated_at: string;
  history: DemandPoint[];
  forecast: ForecastPoint[];
  peak_forecast_mw: number;
  peak_forecast_time: string;
}

interface HistoryRow {
  time: string;
  demand_mw: number;
  temperature_c: number | null;
  solar_generation_mw: number;
  ev_load_mw: number;
  is_holiday: boolean;
}

export async function loadHistory(region: string, days = 60): Promise<HistoryRow[]> {
  const supabase = getSupabaseServer();
  const cutoff = new Date(Date.now() - days * 86400_000).toISOString();
  const { data, error } = await supabase
    .from("demand_readings")
    .select("time, demand_mw, temperature_c, solar_generation_mw, ev_load_mw, is_holiday")
    .eq("region", region)
    .gte("time", cutoff)
    .order("time", { ascending: true });

  if (error) throw error;
  return (data ?? []) as HistoryRow[];
}

function hourOfDay(date: Date): number {
  return date.getUTCHours() + date.getUTCMinutes() / 60;
}

function dayOfWeek(date: Date): number {
  return date.getUTCDay();
}

function monthOfYear(date: Date): number {
  return date.getUTCMonth() + 1;
}

function isHoliday(date: Date): boolean {
  return date.getUTCMonth() === 11 && (date.getUTCDate() === 25 || date.getUTCDate() === 26);
}

function buildFeatures(date: Date, tempC: number | null): number[] {
  const hour = hourOfDay(date);
  const dow = dayOfWeek(date);
  const month = monthOfYear(date);
  return [
    Math.sin((2 * Math.PI * hour) / 24),
    Math.cos((2 * Math.PI * hour) / 24),
    Math.sin((2 * Math.PI * dow) / 7),
    Math.cos((2 * Math.PI * dow) / 7),
    Math.sin((2 * Math.PI * month) / 12),
    Math.cos((2 * Math.PI * month) / 12),
    tempC ?? 0,
    isHoliday(date) ? 1 : 0,
  ];
}

interface TrainedModel {
  weights: Float64Array;
  bias: number;
  trainedRows: number;
}

const modelCache: Record<string, TrainedModel> = {};

function trainLinearRegression(features: number[][], targets: number[]): TrainedModel {
  const n = features.length;
  const dim = features[0].length;
  const lr = 0.001;
  const epochs = 200;

  const weights = new Float64Array(dim);
  let bias = 0;

  for (let epoch = 0; epoch < epochs; epoch++) {
    for (let i = 0; i < n; i++) {
      const x = features[i];
      let pred = bias;
      for (let j = 0; j < dim; j++) pred += weights[j] * x[j];
      const error = pred - targets[i];
      bias -= lr * error;
      for (let j = 0; j < dim; j++) weights[j] -= lr * error * x[j];
    }
  }

  return { weights, bias, trainedRows: n };
}

function predict(model: TrainedModel, features: number[]): number {
  let pred = model.bias;
  for (let j = 0; j < features.length; j++) pred += model.weights[j] * features[j];
  return pred;
}

function getOrTrainModels(region: string, history: HistoryRow[]): TrainedModel {
  const cached = modelCache[region];
  if (cached && cached.trainedRows === history.length) return cached;

  const features = history.map((r) => {
    const date = new Date(r.time);
    return buildFeatures(date, r.temperature_c);
  });
  const targets = history.map((r) => r.demand_mw);

  const model = trainLinearRegression(features, targets);
  modelCache[region] = model;
  return model;
}

async function getFutureTemperatures(
  region: string,
  futureTimes: Date[],
): Promise<(number | null)[]> {
  const hasTemp = REGION_PROFILES[region]?.has_temperature ?? true;
  if (!hasTemp) return futureTimes.map(() => null);

  const cacheKey = makeKey("weather-forecast", region);
  const cached = cacheGet<{ time: string; temp: number }[]>(cacheKey);
  if (cached) {
    const tempMap = new Map(cached.map((r) => [r.time, r.temp]));
    return futureTimes.map((t) => {
      const key = t.toISOString().slice(0, 13) + ":00";
      return tempMap.get(key) ?? null;
    });
  }

  try {
    const [lat, lon] = REGION_COORDS[region] ?? [36.75, -119.77];
    const res = await fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
        `&hourly=temperature_2m&forecast_days=3&timezone=UTC`,
      { signal: AbortSignal.timeout(15000) },
    );
    if (!res.ok) throw new Error(`Weather API ${res.status}`);
    const data = await res.json();
    const times: string[] = data.hourly.time;
    const temps: number[] = data.hourly.temperature_2m;

    const tempRecords = times.map((t, i) => ({ time: t, temp: temps[i] }));
    cacheSet(cacheKey, tempRecords);

    const tempMap = new Map(tempRecords.map((r) => [r.time, r.temp]));
    return futureTimes.map((t) => {
      const key = t.toISOString().slice(0, 13) + ":00";
      return tempMap.get(key) ?? null;
    });
  } catch {
    return futureTimes.map(() => null);
  }
}

export async function forecast(
  region: string,
  regionProfile: { has_temperature: boolean },
  horizonHours = 24,
): Promise<ForecastData> {
  const history = await loadHistory(region);
  if (history.length === 0) {
    throw new Error(`No historical demand data for region '${region}'. Seed the database first.`);
  }

  const model = getOrTrainModels(region, history);

  const now = new Date();
  now.setUTCMinutes(0, 0, 0);
  const futureTimes: Date[] = [];
  for (let i = 1; i <= horizonHours; i++) {
    futureTimes.push(new Date(now.getTime() + i * 3600_000));
  }

  const futureTemps = await getFutureTemperatures(region, futureTimes);

  const predictions = futureTimes.map((t, i) => {
    const features = buildFeatures(t, futureTemps[i]);
    const median = predict(model, features);
    const bandWidth = median * 0.08;
    return {
      time: t.toISOString(),
      predicted_demand_mw: Math.round(median * 100) / 100,
      lower_bound_mw: Math.round((median - bandWidth) * 100) / 100,
      upper_bound_mw: Math.round((median + bandWidth) * 100) / 100,
    };
  });

  let peakIdx = 0;
  for (let i = 1; i < predictions.length; i++) {
    if (predictions[i].predicted_demand_mw > predictions[peakIdx].predicted_demand_mw) peakIdx = i;
  }

  const recentHistory: DemandPoint[] = history.slice(-48).map((r) => ({
    time: r.time,
    demand_mw: r.demand_mw,
    temperature_c: r.temperature_c,
    solar_generation_mw: r.solar_generation_mw,
    ev_load_mw: r.ev_load_mw,
  }));

  return {
    region,
    generated_at: new Date().toISOString(),
    history: recentHistory,
    forecast: predictions,
    peak_forecast_mw: predictions[peakIdx].predicted_demand_mw,
    peak_forecast_time: predictions[peakIdx].time,
  };
}

export async function forecastWhatIf(
  region: string,
  regionProfile: { has_temperature: boolean },
  demandMultiplier: number,
  horizonHours = 24,
): Promise<ForecastData & { demand_multiplier: number }> {
  const base = await forecast(region, regionProfile, horizonHours);

  const scaledPoints = base.forecast.map((p) => ({
    time: p.time,
    predicted_demand_mw: Math.round(p.predicted_demand_mw * demandMultiplier * 100) / 100,
    lower_bound_mw: Math.round(p.lower_bound_mw * demandMultiplier * 100) / 100,
    upper_bound_mw: Math.round(p.upper_bound_mw * demandMultiplier * 100) / 100,
  }));

  let peakIdx = 0;
  for (let i = 1; i < scaledPoints.length; i++) {
    if (scaledPoints[i].predicted_demand_mw > scaledPoints[peakIdx].predicted_demand_mw) peakIdx = i;
  }

  return {
    ...base,
    forecast: scaledPoints,
    peak_forecast_mw: scaledPoints[peakIdx].predicted_demand_mw,
    peak_forecast_time: scaledPoints[peakIdx].time,
    demand_multiplier: demandMultiplier,
  };
}
