import { NextRequest, NextResponse } from "next/server";
import { REGION_PROFILES } from "@/lib/regions";
import { checkRegionForSurge } from "@/lib/surge-watcher";

export async function POST(req: NextRequest) {
  const region = req.nextUrl.searchParams.get("region");
  if (!region || !(region in REGION_PROFILES))
    return NextResponse.json({ detail: `Unknown region '${region}'.` }, { status: 404 });

  const event = await checkRegionForSurge(region, REGION_PROFILES[region], true);
  if (!event)
    return NextResponse.json({ detail: "Could not trigger a demo surge — a pending event may already exist, or there's no seeded demand data." }, { status: 409 });
  return NextResponse.json(event);
}
