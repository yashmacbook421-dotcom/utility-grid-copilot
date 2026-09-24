import { NextResponse } from "next/server";
import { REGION_PROFILES } from "@/lib/regions";
import { computeRegionStatus } from "@/lib/surge-watcher";

export async function GET() {
  const statuses: Record<string, unknown>[] = [];
  for (const [region, profile] of Object.entries(REGION_PROFILES)) {
    const status = await computeRegionStatus(region, profile);
    if (status) statuses.push(status);
  }
  return NextResponse.json({ regions: statuses });
}
