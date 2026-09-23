import { NextRequest, NextResponse } from "next/server";
import { getSupabaseServer } from "@/lib/supabase-server";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { request_log_id, rating, reason, note } = body;

  const supabase = getSupabaseServer();
  const { data: log } = await supabase.from("request_logs").select("id").eq("id", request_log_id).single();
  if (!log) return NextResponse.json({ detail: `No request with id '${request_log_id}'.` }, { status: 404 });

  const { data, error } = await supabase
    .from("answer_feedback")
    .insert({ request_log_id, rating, reason: reason ?? null, note: note ?? null })
    .select("*")
    .single();
  if (error) return NextResponse.json({ detail: error.message }, { status: 500 });
  return NextResponse.json(data);
}
