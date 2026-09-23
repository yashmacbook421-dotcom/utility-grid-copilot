import { NextRequest, NextResponse } from "next/server";
import { getSupabaseServer } from "@/lib/supabase-server";
import { getCustomer } from "@/lib/customer-tools";

export async function GET() {
  const supabase = getSupabaseServer();
  const { data, error } = await supabase
    .from("customer_cases")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(100);
  if (error) return NextResponse.json({ detail: error.message }, { status: 500 });
  return NextResponse.json(data ?? []);
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const { agent_id, customer_id, service_area } = body;

  if (customer_id && !getCustomer(customer_id))
    return NextResponse.json({ detail: `No customer with id '${customer_id}'.` }, { status: 404 });

  const supabase = getSupabaseServer();
  const { data, error } = await supabase
    .from("customer_cases")
    .insert({
      agent_id,
      customer_id: customer_id ?? null,
      service_area: service_area ?? null,
    })
    .select("*")
    .single();
  if (error) return NextResponse.json({ detail: error.message }, { status: 500 });
  return NextResponse.json(data);
}
