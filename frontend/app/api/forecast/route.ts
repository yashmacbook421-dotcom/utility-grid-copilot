import { NextRequest, NextResponse } from "next/server";
import { forecast, forecastWhatIf } from "@/lib/forecasting";
import { REGION_PROFILES } from "@/lib/regions";

export async function GET(req: NextRequest) {
  const region = req.nextUrl.searchParams.get("region");
  const horizonHours = parseInt(req.nextUrl.searchParams.get("horizon_hours") ?? "24", 10);

  if (!region || !(region in REGION_PROFILES))
    return NextResponse.json({ detail: `Unknown region '${region}'. Valid: ${Object.keys(REGION_PROFILES)}` }, { status: 404 });

  try {
    const result = await forecast(region, REGION_PROFILES[region], Math.min(Math.max(horizonHours, 1), 72));
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json({ detail: e instanceof Error ? e.message : String(e) }, { status: 404 });
  }
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { region, demand_multiplier, horizon_hours } = body;

  if (!region || !(region in REGION_PROFILES))
    return NextResponse.json({ detail: `Unknown region '${region}'.` }, { status: 404 });

  try {
    const result = await forecastWhatIf(region, REGION_PROFILES[region], demand_multiplier, horizon_hours ?? 24);
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json({ detail: e instanceof Error ? e.message : String(e) }, { status: 404 });
  }
}
