import { NextRequest, NextResponse } from "next/server";
import { getSupabaseServer } from "@/lib/supabase-server";
import { REGION_PROFILES } from "@/lib/regions";
import { checkRegionForSurge, computeRegionStatus } from "@/lib/surge-watcher";

export async function GET(req: NextRequest) {
  const status = req.nextUrl.searchParams.get("status");
  const region = req.nextUrl.searchParams.get("region");
  const supabase = getSupabaseServer();
  let query = supabase.from("surge_events").select("*").order("created_at", { ascending: false });
  if (status) query = query.eq("status", status);
  if (region) query = query.eq("region", region);
  const { data, error } = await query;
  if (error) return NextResponse.json({ detail: error.message }, { status: 500 });
  return NextResponse.json(data ?? []);
}


