-- SEAM database initialization
-- Run once by Docker entrypoint; idempotent.

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS postgis CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'seam_app') THEN
        CREATE ROLE seam_app LOGIN PASSWORD 'changeme_app';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'seam_promote') THEN
        CREATE ROLE seam_promote LOGIN PASSWORD 'changeme_promote';
    END IF;
END
$$;

GRANT ALL ON DATABASE seam TO seam_app;
GRANT ALL ON SCHEMA public TO seam_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO seam_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO seam_app;
