import { NextResponse } from "next/server";
import { REGION_PROFILES } from "@/lib/regions";

export async function GET() {
  return NextResponse.json({ regions: Object.keys(REGION_PROFILES) });
}
