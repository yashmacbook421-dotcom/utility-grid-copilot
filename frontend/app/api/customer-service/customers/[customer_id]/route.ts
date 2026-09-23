import { NextRequest, NextResponse } from "next/server";
import { getCustomer, getCustomerBill } from "@/lib/customer-tools";

export async function GET(_req: NextRequest, { params }: { params: { customer_id: string } }) {
  const customer = getCustomer(params.customer_id);
  if (!customer) return NextResponse.json({ detail: `No customer with id '${params.customer_id}'.` }, { status: 404 });
  const bill = getCustomerBill(params.customer_id);
  return NextResponse.json({ customer, bill });
}
