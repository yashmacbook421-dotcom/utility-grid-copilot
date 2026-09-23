import { NextResponse } from "next/server";
import { AREA_DOCUMENT_TYPES } from "@/lib/delivery-assist";

export async function GET() {
  return NextResponse.json(Object.keys(AREA_DOCUMENT_TYPES));
}
