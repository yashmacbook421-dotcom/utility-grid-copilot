import { NextRequest, NextResponse } from "next/server";
import { ingestDocument } from "@/lib/rag";
import { getSupabaseServer } from "@/lib/supabase-server";
import { EIA_RESPONDENTS } from "@/lib/regions";
import { config } from "@/lib/config";
import * as fs from "fs";
import * as path from "path";

const PROCEDURES_DIR = path.join(process.cwd(), "docs", "procedures");
const CUSTOMER_SERVICE_DIR = path.join(process.cwd(), "docs", "customer_service");
const DELIVERY_ASSIST_DIR = path.join(process.cwd(), "docs", "delivery_assist");

const SAFETY_DOC_FILES = new Set([
  "safety-procedures.md",
  "downed-power-line-procedures.md",
  "emergency-response-procedures.md",
]);

const DELIVERY_ASSIST_DOC_TYPES: Record<string, string> = {
  "fixed-recurring-charges.md": "billing_configuration",
  "billing-adjustment-reason-codes.md": "billing_configuration",
  "rate-schedule-effective-dating.md": "rate_configuration",
  "tiered-and-time-of-use-rates.md": "rate_configuration",
  "usage-validation-lifecycle.md": "meter_data_management",
  "missing-interval-data-handling.md": "meter_data_management",
  "work-order-prioritization-basics.md": "work_asset_management",
};

function titleFromFilename(filename: string): string {
  return filename.replace(/\.md$/, "").replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export async function POST(req: NextRequest) {
  const supabase = getSupabaseServer();
  const { count } = await supabase.from("documents").select("*", { count: "exact", head: true });
  if ((count ?? 0) > 0) {
    return NextResponse.json({ message: "Database already seeded", documents: count });
  }

  const results: string[] = [];

  // 1. Ingest procedure docs
  for (const file of fs.readdirSync(PROCEDURES_DIR).sort()) {
    if (!file.endsWith(".md")) continue;
    const content = fs.readFileSync(path.join(PROCEDURES_DIR, file), "utf-8");
    const title = titleFromFilename(file);
    const chunks = await ingestDocument({ source: file, title, content });
    results.push(`procedures/${file}: ${chunks.length} chunks`);
  }

  // 2. Ingest customer service docs
  for (const file of fs.readdirSync(CUSTOMER_SERVICE_DIR).sort()) {
    if (!file.endsWith(".md")) continue;
    const content = fs.readFileSync(path.join(CUSTOMER_SERVICE_DIR, file), "utf-8");
    const title = titleFromFilename(file);
    const documentType = SAFETY_DOC_FILES.has(file) ? "safety_procedure" : "customer_service_procedure";
    const chunks = await ingestDocument({
      source: file, title, content,
      organization: "customer_service", documentType,
    });
    results.push(`customer_service/${file}: ${chunks.length} chunks (${documentType})`);
  }

  // 3. Ingest delivery assist docs
  for (const file of fs.readdirSync(DELIVERY_ASSIST_DIR).sort()) {
    if (!file.endsWith(".md")) continue;
    const content = fs.readFileSync(path.join(DELIVERY_ASSIST_DIR, file), "utf-8");
    const title = titleFromFilename(file);
    const documentType = DELIVERY_ASSIST_DOC_TYPES[file] ?? "delivery_assist_pattern";
    const chunks = await ingestDocument({
      source: file, title, content,
      organization: "delivery_assist", documentType,
    });
    results.push(`delivery_assist/${file}: ${chunks.length} chunks (${documentType})`);
  }

  // 4. Seed demand data from EIA if API key is configured
  let demandRows = 0;
  if (config.eiaApiKey) {
    for (const [region, respondent] of Object.entries(EIA_RESPONDENTS)) {
      try {
        const rows = await fetchEiaDemand(region, respondent, config.eiaApiKey);
        if (rows.length > 0) {
          const { error } = await supabase.from("demand_readings").insert(rows);
          if (!error) {
            demandRows += rows.length;
            results.push(`demand/${region}: ${rows.length} rows`);
          }
        }
      } catch (e) {
        results.push(`demand/${region}: failed - ${e instanceof Error ? e.message : String(e)}`);
      }
    }
  } else {
    // Seed synthetic demand data
    const syntheticRows = generateSyntheticDemand();
  if (syntheticRows.length > 0) {
    const { error } = await supabase.from("demand_readings").insert(syntheticRows);
    if (!error) {
      demandRows += syntheticRows.length;
      results.push(`demand/synthetic: ${syntheticRows.length} rows`);
    }
  }
  }

  return NextResponse.json({ message: "Seed complete", results, demandRows });
}

async function fetchEiaDemand(region: string, respondent: string, apiKey: string): Promise<Record<string, unknown>[]> {
  const end = new Date();
  end.setUTCMinutes(0, 0, 0);
  const start = new Date(end.getTime() - 90 * 86400_000);
  const rows: Record<string, unknown>[] = [];
  let offset = 0;
  while (true) {
    const params = new URLSearchParams({
      api_key: apiKey,
      frequency: "hourly",
      "data[0]": "value",
      "facets[respondent][]": respondent,
      "facets[type][]": "D",
      start: start.toISOString().slice(0, 13),
      end: end.toISOString().slice(0, 13),
      "sort[0][column]": "period",
      "sort[0][direction]": "asc",
      offset: String(offset),
      length: "5000",
    });
    const res = await fetch(`https://api.eia.gov/v2/electricity/rto/region-data/data/?${params}`, { signal: AbortSignal.timeout(30000) });
    if (!res.ok) throw new Error(`EIA API ${res.status}`);
    const data = await res.json();
    const page = data.response.data;
    for (const r of page) {
      const time = r.period + ":00:00Z";
      const date = new Date(time);
      rows.push({
        time: date.toISOString(),
        region,
        demand_mw: parseFloat(r.value),
        temperature_c: null,
        solar_generation_mw: 0,
        ev_load_mw: 0,
        is_holiday: date.getUTCMonth() === 11 && (date.getUTCDate() === 25 || date.getUTCDate() === 26),
      });
    }
    if (page.length < 5000) break;
    offset += 5000;
  }
  return rows;
}

function generateSyntheticDemand(): Record<string, unknown>[] {
  const rows: Record<string, unknown>[] = [];
  const regions = ["california", "smud", "georgia"];
  const baseDemand: Record<string, number> = { california: 28000, smud: 3000, georgia: 11000 };
  const now = new Date();
  now.setUTCMinutes(0, 0, 0);
  for (const region of regions) {
    const base = baseDemand[region];
    for (let h = 0; h < 90 * 24; h++) {
      const time = new Date(now.getTime() - (90 * 24 - h) * 3600_000);
      const hour = time.getUTCHours();
      const dow = time.getUTCDay();
      const month = time.getUTCMonth();
      const seasonalFactor = 1 + 0.3 * Math.sin((2 * Math.PI * (month - 5)) / 12);
      const dailyFactor = 1 + 0.25 * Math.sin((2 * Math.PI * (hour - 6)) / 24);
      const weekendFactor = dow === 0 || dow === 6 ? 0.85 : 1.0;
      const noise = 0.95 + Math.random() * 0.1;
      const demand = Math.round(base * seasonalFactor * dailyFactor * weekendFactor * noise);
      rows.push({
        time: time.toISOString(),
        region,
        demand_mw: demand,
        temperature_c: 15 + 10 * Math.sin((2 * Math.PI * (month - 5)) / 12) + 5 * Math.sin((2 * Math.PI * hour) / 24),
        solar_generation_mw: 0,
        ev_load_mw: 0,
        is_holiday: time.getUTCMonth() === 11 && (time.getUTCDate() === 25 || time.getUTCDate() === 26),
      });
    }
  }
  return rows;
}
