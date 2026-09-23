import { NextResponse } from "next/server";
import { listCustomers, getCustomer, getCustomerBill } from "@/lib/customer-tools";

export async function GET() {
  return NextResponse.json(listCustomers());
}
