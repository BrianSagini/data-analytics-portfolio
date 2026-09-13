#!/usr/bin/env bash
# Runs once, automatically, the first time the postgres data volume is created
# (official postgres image behavior for anything in /docker-entrypoint-initdb.d).
# Idempotent guards are still used throughout since a rebuild without wiping
# the volume must not fail on "already exists".
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_USER" <<-EOSQL
    -- Airflow metadata database + its own role
    SELECT 'CREATE DATABASE ${AIRFLOW_DB_NAME}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${AIRFLOW_DB_NAME}')\gexec

    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${AIRFLOW_DB_USER}') THEN
            CREATE ROLE ${AIRFLOW_DB_USER} LOGIN PASSWORD '${AIRFLOW_DB_PASSWORD}';
        END IF;
    END
    \$\$;
    GRANT ALL PRIVILEGES ON DATABASE ${AIRFLOW_DB_NAME} TO ${AIRFLOW_DB_USER};

    -- Analytics database
    SELECT 'CREATE DATABASE ${ANALYTICS_DB_NAME}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${ANALYTICS_DB_NAME}')\gexec

    -- Read-only role for dashboards
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${ANALYTICS_RO_USER}') THEN
            CREATE ROLE ${ANALYTICS_RO_USER} LOGIN PASSWORD '${ANALYTICS_RO_PASSWORD}';
        END IF;
    END
    \$\$;
    GRANT CONNECT ON DATABASE ${ANALYTICS_DB_NAME} TO ${ANALYTICS_RO_USER};
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$AIRFLOW_DB_NAME" <<-EOSQL
    -- Postgres 15+ no longer grants CREATE on "public" to all users by
    -- default -- Airflow's own db migrate needs to create tables there.
    GRANT ALL ON SCHEMA public TO ${AIRFLOW_DB_USER};
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$ANALYTICS_DB_NAME" <<-EOSQL
    CREATE SCHEMA IF NOT EXISTS climate_risk AUTHORIZATION ${POSTGRES_USER};
    CREATE SCHEMA IF NOT EXISTS dark_store    AUTHORIZATION ${POSTGRES_USER};
    CREATE SCHEMA IF NOT EXISTS hiring_bias   AUTHORIZATION ${POSTGRES_USER};
    CREATE SCHEMA IF NOT EXISTS fraud_pattern AUTHORIZATION ${POSTGRES_USER};

    GRANT USAGE ON SCHEMA climate_risk, dark_store, hiring_bias, fraud_pattern TO ${ANALYTICS_RO_USER};

    ALTER DEFAULT PRIVILEGES IN SCHEMA climate_risk GRANT SELECT ON TABLES TO ${ANALYTICS_RO_USER};
    ALTER DEFAULT PRIVILEGES IN SCHEMA dark_store GRANT SELECT ON TABLES TO ${ANALYTICS_RO_USER};
    ALTER DEFAULT PRIVILEGES IN SCHEMA hiring_bias GRANT SELECT ON TABLES TO ${ANALYTICS_RO_USER};
    ALTER DEFAULT PRIVILEGES IN SCHEMA fraud_pattern GRANT SELECT ON TABLES TO ${ANALYTICS_RO_USER};
EOSQL
