-- =============================================================================
-- Postgres bootstrap: create the three tennetctl roles
-- Runs once on first docker compose up via docker-entrypoint-initdb.d
-- =============================================================================

-- Read role — SELECT only, used by GET endpoints and reporting
CREATE ROLE tennetctl_read WITH LOGIN PASSWORD 'tennetctl_read_dev' NOINHERIT;

-- Write role — SELECT + DML, used by the FastAPI application at runtime
CREATE ROLE tennetctl_write WITH LOGIN PASSWORD 'tennetctl_write_dev' NOINHERIT;

-- Admin role is the POSTGRES_USER (tennetctl_admin) created by the image.
-- It has full DDL + DML and is used by the migration runner only.

-- Grant connect on the database to all roles
GRANT CONNECT ON DATABASE tennetctl TO tennetctl_read;
GRANT CONNECT ON DATABASE tennetctl TO tennetctl_write;

-- Default privileges so future schemas created by tennetctl_admin are
-- automatically accessible to the read and write roles.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO tennetctl_read;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tennetctl_write;
