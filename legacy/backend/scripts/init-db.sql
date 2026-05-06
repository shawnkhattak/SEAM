-- Run once on first container start (docker-entrypoint-initdb.d).
-- Creates extensions and application roles.
-- Alembic migrations handle all schema DDL after this.

-- Extensions (timescaledb + postgis ship with timescale/timescaledb-ha image)
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Application roles
DO $$
BEGIN
    -- App process: read/write operational tables
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'oceansx_app') THEN
        CREATE ROLE oceansx_app LOGIN PASSWORD 'changeme_app';
    END IF;

    -- Operations Swarm: staging writes only
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'oceansx_ops') THEN
        CREATE ROLE oceansx_ops LOGIN PASSWORD 'changeme_ops';
    END IF;

    -- Approval flow: promotes staging → production
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'oceansx_promote') THEN
        CREATE ROLE oceansx_promote LOGIN PASSWORD 'changeme_promote';
    END IF;

    -- Read-only analytics
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'oceansx_readonly') THEN
        CREATE ROLE oceansx_readonly LOGIN PASSWORD 'changeme_readonly';
    END IF;
END
$$;

-- Grant connect on database
GRANT CONNECT ON DATABASE oceansx TO oceansx_app, oceansx_ops, oceansx_promote, oceansx_readonly;

-- Default privileges — schema permissions are finalized by Alembic migrations
GRANT USAGE ON SCHEMA public TO oceansx_app, oceansx_ops, oceansx_promote, oceansx_readonly;
