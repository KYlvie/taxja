-- PostgreSQL extensions for Taxja production
-- Loaded automatically on first database init

-- Query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Trigram index support (fuzzy text search for transactions)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
