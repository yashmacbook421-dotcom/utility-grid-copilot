export const config = {
  anthropicApiKey: process.env.ANTHROPIC_API_KEY ?? "",
  eiaApiKey: process.env.EIA_API_KEY ?? "",
  claudeModel: process.env.CLAUDE_MODEL ?? "claude-sonnet-5",
  claudeRouterModel: process.env.CLAUDE_ROUTER_MODEL ?? "claude-haiku-4-5",
  embeddingDim: 384,
  dailySpendCapUsd: parseFloat(process.env.DAILY_SPEND_CAP_USD ?? "5.00"),
  slackWebhookUrl: process.env.SLACK_WEBHOOK_URL ?? "",
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.VITE_SUPABASE_URL || "",
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.VITE_SUPABASE_ANON_KEY || "",
  supabaseServiceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY || "",
};

export const PRICING: Record<string, { input_per_mtok: number; output_per_mtok: number }> = {
  "claude-sonnet-5": { input_per_mtok: 2.0, output_per_mtok: 10.0 },
  "claude-haiku-4-5": { input_per_mtok: 1.0, output_per_mtok: 5.0 },
};

export function estimateCostUsd(model: string, inputTokens: number, outputTokens: number): number | null {
  const rates = PRICING[model];
  if (!rates) return null;
  return (
    (inputTokens / 1_000_000) * rates.input_per_mtok +
    (outputTokens / 1_000_000) * rates.output_per_mtok
  );
}
