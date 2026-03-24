#!/bin/sh
set -e

OUT=/tmp/init.sql

echo "-- Taxja Database Initialization Script" > $OUT
echo "-- Auto-generated from live database" >> $OUT
echo "" >> $OUT

echo "-- PART 1: Schema (types, tables, indexes, constraints)" >> $OUT
pg_dump -U taxja -d taxja --schema-only --no-owner --no-privileges --no-comments >> $OUT 2>/dev/null

echo "" >> $OUT
echo "-- PART 2: Seed Data (reference tables)" >> $OUT
pg_dump -U taxja -d taxja --data-only --no-owner --no-privileges --inserts --table=plans --table=tax_configurations --table=credit_cost_configs --table=credit_topup_packages >> $OUT 2>/dev/null

echo "" >> $OUT
echo "-- PART 3: Alembic version stamp" >> $OUT
printf "INSERT INTO public.alembic_version (version_num) VALUES ('068_resync_doctypes') ON CONFLICT DO NOTHING;\n" >> $OUT

echo "Done: $(wc -l < $OUT) lines"
