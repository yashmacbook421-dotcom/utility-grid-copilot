-- Runs automatically on first container start (mounted into /docker-entrypoint-initdb.d).
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;
