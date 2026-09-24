import { createClient } from "@supabase/supabase-js";
import { config } from "./config";

export function getSupabaseServer() {
  return createClient(config.supabaseUrl, config.supabaseServiceRoleKey || config.supabaseAnonKey, {
    auth: { persistSession: false },
  });
}
