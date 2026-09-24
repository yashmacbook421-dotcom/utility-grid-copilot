import { NextRequest, NextResponse } from "next/server";
import { getSupabaseServer } from "@/lib/supabase-server";

export async function POST(req: NextRequest, { params }: { params: { surge_id: string } }) {
  const body = await req.json().catch(() => ({}));
  const supabase = getSupabaseServer();
  const { data: event, error } = await supabase
    .from("surge_events")
    .update({ status: "rejected", resolved_at: new Date().toISOString(), resolved_note: body.note ?? null })
    .eq("id", params.surge_id)
    .select("*")
    .single();
  if (error || !event) return NextResponse.json({ detail: `No surge event with id '${params.surge_id}'.` }, { status: 404 });
  return NextResponse.json(event);
}
