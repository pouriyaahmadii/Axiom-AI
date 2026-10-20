#!/bin/bash
# ==============================================================================
# PostgreSQL Initialization Script: AgentOps
# Creates separate, least-privilege databases and roles for AgentOps and n8n.
# Executed automatically by official postgres container on first volume boot.
# ==============================================================================

set -euo pipefail

echo "==> [PostgreSQL Init] Initializing separate databases and users for AgentOps and n8n..."

# Defaults if not explicitly set
AGENTOPS_USER="${AGENTOPS_DB_USER:-agentops_user}"
AGENTOPS_PASS="${AGENTOPS_DB_PASSWORD:-agentops_pass}"
AGENTOPS_DB="${AGENTOPS_DB_NAME:-agentops_db}"

N8N_USER="${N8N_DB_USER:-n8n_user}"
N8N_PASS="${N8N_DB_PASSWORD:-n8n_pass}"
N8N_DB="${N8N_DB_NAME:-n8n_db}"

# Execute SQL commands as the administrative superuser
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- 1. Create AgentOps Application Role & Database
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$AGENTOPS_USER') THEN
            CREATE ROLE $AGENTOPS_USER WITH LOGIN PASSWORD '$AGENTOPS_PASS';
        END IF;
    END
    \$\$;

    SELECT 'CREATE DATABASE $AGENTOPS_DB OWNER $AGENTOPS_USER'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$AGENTOPS_DB')\gexec

    GRANT ALL PRIVILEGES ON DATABASE $AGENTOPS_DB TO $AGENTOPS_USER;

    -- 2. Create n8n Automation Role & Database
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$N8N_USER') THEN
            CREATE ROLE $N8N_USER WITH LOGIN PASSWORD '$N8N_PASS';
        END IF;
    END
    \$\$;

    SELECT 'CREATE DATABASE $N8N_DB OWNER $N8N_USER'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$N8N_DB')\gexec

    GRANT ALL PRIVILEGES ON DATABASE $N8N_DB TO $N8N_USER;
EOSQL

# Grant schema privileges inside AgentOps DB
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$AGENTOPS_DB" <<-EOSQL
    GRANT ALL ON SCHEMA public TO $AGENTOPS_USER;
    ALTER SCHEMA public OWNER TO $AGENTOPS_USER;
EOSQL

# Grant schema privileges inside n8n DB
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$N8N_DB" <<-EOSQL
    GRANT ALL ON SCHEMA public TO $N8N_USER;
    ALTER SCHEMA public OWNER TO $N8N_USER;
EOSQL

echo "==> [PostgreSQL Init] Database initialization completed successfully."
