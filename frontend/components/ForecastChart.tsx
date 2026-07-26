"use client";

import { Area, CartesianGrid, ComposedChart, Line, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ForecastResponse } from "@/lib/types";

type Row = {
  time: string;
  label: string;
  actual?: number;
  predicted?: number;
  lower?: number;
  bandRange?: number;
};

function formatLabel(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" });
}

function buildRows(data: ForecastResponse): Row[] {
  const history: Row[] = data.history.map((p) => ({
    time: p.time,
    label: formatLabel(p.time),
    actual: p.demand_mw,
  }));

  const lastHistory = history[history.length - 1];
  const bridge: Row[] = lastHistory
    ? [{ ...lastHistory, predicted: lastHistory.actual, lower: lastHistory.actual, bandRange: 0 }]
    : [];

  const forecast: Row[] = data.forecast.map((p) => ({
    time: p.time,
    label: formatLabel(p.time),
    predicted: p.predicted_demand_mw,
    lower: p.lower_bound_mw,
    bandRange: p.upper_bound_mw - p.lower_bound_mw,
  }));

  if (lastHistory) {
    return [...history.slice(0, -1), ...bridge, ...forecast];
  }
  return [...history, ...forecast];
}

function ChartTooltip({ active, payload }: any) {
  if (!active || !payload || payload.length === 0) return null;
  const row: Row = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-time">{row.label}</p>
      {row.actual !== undefined && (
        <div className="chart-tooltip-row">
          <span className="chart-tooltip-key" style={{ background: "var(--series-1)" }} />
          <span className="chart-tooltip-name">Actual</span>
          <span className="chart-tooltip-value">{Math.round(row.actual).toLocaleString()} MW</span>
        </div>
      )}
      {row.predicted !== undefined && (
        <div className="chart-tooltip-row">
          <span className="chart-tooltip-key" style={{ background: "var(--series-2)" }} />
          <span className="chart-tooltip-name">Forecast</span>
          <span className="chart-tooltip-value">{Math.round(row.predicted).toLocaleString()} MW</span>
        </div>
      )}
      {row.lower !== undefined && row.bandRange !== undefined && row.bandRange > 0 && (
        <div className="chart-tooltip-row">
          <span className="chart-tooltip-name">10–90% range</span>
          <span className="chart-tooltip-value">
            {Math.round(row.lower).toLocaleString()}–{Math.round(row.lower + row.bandRange).toLocaleString()} MW
          </span>
        </div>
      )}
    </div>
  );
}

export default function ForecastChart({ data }: { data: ForecastResponse }) {
  const rows = buildRows(data);
  const peakRow = rows.find((r) => r.time === data.peak_forecast_time || new Date(r.time).getTime() === new Date(data.peak_forecast_time).getTime());

  return (
    <div>
      <div className="legend-row">
        <span className="legend-item">
          <span className="legend-swatch-line" style={{ background: "var(--series-1)" }} />
          Actual demand
        </span>
        <span className="legend-item">
          <span className="legend-swatch-line" style={{ background: "var(--series-2)" }} />
          Forecast
        </span>
        <span className="legend-item">
          <span className="legend-swatch-band" style={{ background: "var(--series-2-band)" }} />
          10–90% range
        </span>
      </div>
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={rows} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--gridline)" vertical={false} />
          <XAxis
            dataKey="label"
            stroke="var(--axis)"
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "var(--gridline)" }}
            minTickGap={40}
          />
          <YAxis
            stroke="var(--axis)"
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={56}
            tickFormatter={(v: number) => `${Math.round(v).toLocaleString()}`}
            domain={["auto", "auto"]}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--axis)", strokeWidth: 1 }} />
          <Area dataKey="lower" stackId="band" stroke="none" fill="none" isAnimationActive={false} />
          <Area dataKey="bandRange" stackId="band" stroke="none" fill="var(--series-2-band)" isAnimationActive={false} />
          <Line
            dataKey="actual"
            stroke="var(--series-1)"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
          <Line
            dataKey="predicted"
            stroke="var(--series-2)"
            strokeWidth={2}
            strokeDasharray="4 3"
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
          />
          {peakRow && peakRow.predicted !== undefined && (
            <ReferenceDot
              x={peakRow.label}
              y={peakRow.predicted}
              r={4}
              fill="var(--series-2)"
              stroke="var(--surface-1)"
              strokeWidth={2}
              isFront
              label={{
                value: `Peak ${Math.round(peakRow.predicted).toLocaleString()} MW`,
                position: "top",
                fill: "var(--text-secondary)",
                fontSize: 11,
              }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
