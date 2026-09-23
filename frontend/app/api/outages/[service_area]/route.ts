import { NextRequest, NextResponse } from "next/server";
import { getOutageStatus } from "@/lib/customer-tools";
import { SERVICE_AREAS } from "@/lib/demo-data";

export async function GET(_req: NextRequest, { params }: { params: { service_area: string } }) {
  const data = getOutageStatus(params.service_area);
  if (!data)
    return NextResponse.json({ detail: `No outage data for service area '${params.service_area}'. Known areas: ${SERVICE_AREAS}` }, { status: 404 });
  return NextResponse.json(data);
}
