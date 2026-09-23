import { getSupabaseServer } from "./supabase-server";
import { config } from "./config";

export async function todaySpendUsd(): Promise<number> {
  const supabase = getSupabaseServer();
  const startOfDay = new Date();
  startOfDay.setUTCHours(0, 0, 0, 0);

  const { data, error } = await supabase
    .from("request_logs")
    .select("estimated_cost_usd")
    .gte("created_at", startOfDay.toISOString());

  if (error) return 0;
  return (data ?? []).reduce((sum, r) => sum + (r.estimated_cost_usd ?? 0), 0);
}

export async function isOverBudget(): Promise<boolean> {
  if (config.dailySpendCapUsd <= 0) return false;
  return (await todaySpendUsd()) >= config.dailySpendCapUsd;
}

export class BudgetExceededError extends Error {
  status: number;
  constructor(spent: number, cap: number) {
    super(
      `Daily Claude spend cap of $${cap.toFixed(2)} has been reached ($${spent.toFixed(2)} spent today). ` +
        "This endpoint will be available again after the cap resets at midnight UTC."
    );
    this.status = 503;
  }
}

export async function enforceBudget(): Promise<void> {
  const cap = config.dailySpendCapUsd;
  if (cap <= 0) return;
  const spent = await todaySpendUsd();
  if (spent >= cap) throw new BudgetExceededError(spent, cap);
}
