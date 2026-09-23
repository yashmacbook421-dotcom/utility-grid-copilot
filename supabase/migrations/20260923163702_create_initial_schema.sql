
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============ demand_readings ============
CREATE TABLE IF NOT EXISTS demand_readings (
  time timestamptz NOT NULL,
  region text NOT NULL,
  demand_mw double precision NOT NULL,
  temperature_c double precision,
  solar_generation_mw double precision NOT NULL DEFAULT 0.0,
  ev_load_mw double precision NOT NULL DEFAULT 0.0,
  is_holiday boolean NOT NULL DEFAULT false,
  PRIMARY KEY (time, region)
);

-- ============ documents ============
CREATE TABLE IF NOT EXISTS documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  organization text NOT NULL,
  document_type text NOT NULL,
  source_url text NOT NULL,
  publication_date date,
  region text,
  ingested_at timestamptz NOT NULL DEFAULT now()
);

-- ============ document_chunks ============
CREATE TABLE IF NOT EXISTS document_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  content text NOT NULL,
  embedding vector(384) NOT NULL,
  page_number integer,
  section text
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding ON document_chunks
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_id ON document_chunks(document_id);

-- ============ ingestion_runs ============
CREATE TABLE IF NOT EXISTS ingestion_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  source_path_or_url text NOT NULL,
  status text NOT NULL,
  chunks_created integer NOT NULL DEFAULT 0,
  error_message text,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);

-- ============ request_logs ============
CREATE TABLE IF NOT EXISTS request_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  endpoint text NOT NULL,
  region text,
  question text,
  embedding_ms double precision,
  retrieval_ms double precision,
  forecast_ms double precision,
  generation_ms double precision,
  total_ms double precision,
  retrieved_sources jsonb NOT NULL DEFAULT '[]'::jsonb,
  input_tokens integer,
  output_tokens integer,
  estimated_cost_usd double precision,
  status text NOT NULL,
  error_message text
);

CREATE INDEX IF NOT EXISTS idx_request_logs_created_at ON request_logs(created_at DESC);

-- ============ surge_events ============
CREATE TABLE IF NOT EXISTS surge_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  region text NOT NULL,
  forecast_peak_mw double precision NOT NULL,
  baseline_p95_mw double precision NOT NULL,
  peak_forecast_time timestamptz NOT NULL,
  recommended_action text NOT NULL,
  sources jsonb NOT NULL DEFAULT '[]'::jsonb,
  severity text NOT NULL DEFAULT 'medium',
  notified boolean NOT NULL DEFAULT false,
  notification_error text,
  status text NOT NULL DEFAULT 'pending',
  resolved_at timestamptz,
  resolved_note text
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_surge_events_pending_region ON surge_events(region)
  WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_surge_events_created_at ON surge_events(created_at DESC);

-- ============ customer_cases ============
CREATE TABLE IF NOT EXISTS customer_cases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  agent_id text NOT NULL,
  customer_id text,
  service_area text,
  status text NOT NULL DEFAULT 'open',
  messages jsonb NOT NULL DEFAULT '[]'::jsonb,
  escalated boolean NOT NULL DEFAULT false,
  escalation_reason text,
  summary text,
  request_log_ids jsonb NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_customer_cases_created_at ON customer_cases(created_at DESC);

-- ============ answer_feedback ============
CREATE TABLE IF NOT EXISTS answer_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_log_id uuid NOT NULL REFERENCES request_logs(id) ON DELETE CASCADE,
  rating text NOT NULL,
  reason text,
  note text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ============ RLS Policies ============
-- No auth in this demo app; use anon+authenticated for read/write
ALTER TABLE demand_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE request_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE surge_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE answer_feedback ENABLE ROW LEVEL SECURITY;

-- Demand readings: full CRUD for anon+authenticated
CREATE POLICY "select_demand_readings" ON demand_readings FOR SELECT
  TO anon, authenticated USING (true);
CREATE POLICY "insert_demand_readings" ON demand_readings FOR INSERT
  TO anon, authenticated WITH CHECK (true);
CREATE POLICY "update_demand_readings" ON demand_readings FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "delete_demand_readings" ON demand_readings FOR DELETE
  TO anon, authenticated USING (true);

-- Documents: full CRUD
CREATE POLICY "select_documents" ON documents FOR SELECT
  TO anon, authenticated USING (true);
CREATE POLICY "insert_documents" ON documents FOR INSERT
  TO anon, authenticated WITH CHECK (true);
CREATE POLICY "update_documents" ON documents FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "delete_documents" ON documents FOR DELETE
  TO anon, authenticated USING (true);

-- Document chunks: full CRUD
CREATE POLICY "select_document_chunks" ON document_chunks FOR SELECT
  TO anon, authenticated USING (true);
CREATE POLICY "insert_document_chunks" ON document_chunks FOR INSERT
  TO anon, authenticated WITH CHECK (true);
CREATE POLICY "update_document_chunks" ON document_chunks FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "delete_document_chunks" ON document_chunks FOR DELETE
  TO anon, authenticated USING (true);

-- Ingestion runs: full CRUD
CREATE POLICY "select_ingestion_runs" ON ingestion_runs FOR SELECT
  TO anon, authenticated USING (true);
CREATE POLICY "insert_ingestion_runs" ON ingestion_runs FOR INSERT
  TO anon, authenticated WITH CHECK (true);
CREATE POLICY "update_ingestion_runs" ON ingestion_runs FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "delete_ingestion_runs" ON ingestion_runs FOR DELETE
  TO anon, authenticated USING (true);

-- Request logs: full CRUD
CREATE POLICY "select_request_logs" ON request_logs FOR SELECT
  TO anon, authenticated USING (true);
CREATE POLICY "insert_request_logs" ON request_logs FOR INSERT
  TO anon, authenticated WITH CHECK (true);
CREATE POLICY "update_request_logs" ON request_logs FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "delete_request_logs" ON request_logs FOR DELETE
  TO anon, authenticated USING (true);

-- Surge events: full CRUD
CREATE POLICY "select_surge_events" ON surge_events FOR SELECT
  TO anon, authenticated USING (true);
CREATE POLICY "insert_surge_events" ON surge_events FOR INSERT
  TO anon, authenticated WITH CHECK (true);
CREATE POLICY "update_surge_events" ON surge_events FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "delete_surge_events" ON surge_events FOR DELETE
  TO anon, authenticated USING (true);

-- Customer cases: full CRUD
CREATE POLICY "select_customer_cases" ON customer_cases FOR SELECT
  TO anon, authenticated USING (true);
CREATE POLICY "insert_customer_cases" ON customer_cases FOR INSERT
  TO anon, authenticated WITH CHECK (true);
CREATE POLICY "update_customer_cases" ON customer_cases FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "delete_customer_cases" ON customer_cases FOR DELETE
  TO anon, authenticated USING (true);

-- Answer feedback: full CRUD
CREATE POLICY "select_answer_feedback" ON answer_feedback FOR SELECT
  TO anon, authenticated USING (true);
CREATE POLICY "insert_answer_feedback" ON answer_feedback FOR INSERT
  TO anon, authenticated WITH CHECK (true);
CREATE POLICY "update_answer_feedback" ON answer_feedback FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "delete_answer_feedback" ON answer_feedback FOR DELETE
  TO anon, authenticated USING (true);
