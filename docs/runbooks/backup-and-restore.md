# Backup, Restore, and Disaster Recovery Runbook (`docs/runbooks/backup-and-restore.md`)

This runbook establishes verified procedures for backing up, restoring, and safely resetting the persistent data stores of AgentOps: PostgreSQL (`agentops_db`, `n8n_db`), Redis, and n8n volume assets.

---

## 1. Data Store Scope & Recovery Objectives

| Asset | Storage Location | Criticality | Loss Impact |
| :--- | :--- | :--- | :--- |
| **AgentOps Core DB** (`agentops_db`) | PostgreSQL Volume `postgres_data` | High | Loss of run execution plans, step transitions, citations, evidence artifacts, and human approval audit logs. |
| **n8n Automation DB** (`n8n_db`) | PostgreSQL Volume `postgres_data` | Medium | Loss of active workflow configurations, execution logs, and external webhook triggers. |
| **n8n Volume & Key** | `n8n_data` + `.env` (`N8N_ENCRYPTION_KEY`) | High | If encryption key is lost, credentials stored in `n8n_db` are permanently unrecoverable. |
| **Redis Queue & State** | Redis Volume `redis_data` (`appendonly.aof`) | Medium | Loss of inflight Celery job buffers and ephemeral cache keys. Durable run state remains safe in PostgreSQL. |

---

## 2. PostgreSQL Backup Procedures

All backups are performed online without stopping the database container, using `pg_dump` executed inside the `agentops_postgres` container.

### Step 1: Create Backup Directory
```bash
mkdir -p backups/postgres backups/redis backups/n8n
```

### Step 2: Backup AgentOps Application Database
Back up `agentops_db` using the custom compressed archive format (`-Fc`), which supports selective and parallel restoration:
```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

docker compose -p agentops exec -T postgres \
  pg_dump -U agentops_user -d agentops_db -Fc -Z 9 \
  > "backups/postgres/agentops_db_${TIMESTAMP}.dump"
```

### Step 3: Backup n8n Automation Database
Back up `n8n_db` in compressed archive format:
```bash
docker compose -p agentops exec -T postgres \
  pg_dump -U n8n_user -d n8n_db -Fc -Z 9 \
  > "backups/postgres/n8n_db_${TIMESTAMP}.dump"
```

### Step 4: Backup Global Roles & Permissions
Capture global cluster roles (`agentops_user`, `n8n_user`) and system permissions:
```bash
docker compose -p agentops exec -T postgres \
  pg_dumpall -U postgres_admin --globals-only \
  > "backups/postgres/globals_${TIMESTAMP}.sql"
```

---

## 3. PostgreSQL Restoration Procedures

### Restoring `agentops_db` to an Active Cluster

> [!CAUTION]
> Restoring a database drops existing tables and replaces them with data from the backup dump. Ensure all active background workers are stopped before executing a restore.

```bash
# 1. Stop background workers and API to prevent write collisions
docker compose -p agentops stop backend-api backend-worker 2>/dev/null || true

# 2. Restore application schema and data using pg_restore
# Replace BACKUP_FILE with the path to your target dump file
BACKUP_FILE="backups/postgres/agentops_db_20261020_120000.dump"

docker compose -p agentops exec -T postgres \
  pg_restore -U agentops_user -d agentops_db --clean --if-exists --no-owner < "${BACKUP_FILE}"
```

### Restoring to a Brand-New / Empty Cluster
If recovering from a total disk loss or newly initialized `postgres_data` volume:
```bash
# 1. Ensure databases and roles are initialized
docker compose -p agentops up -d postgres
sleep 5

# 2. Restore global roles first (if not created by init-databases.sh)
docker compose -p agentops exec -T postgres \
  psql -U postgres_admin -d postgres < "backups/postgres/globals_*.sql"

# 3. Restore agentops_db
docker compose -p agentops exec -T postgres \
  pg_restore -U agentops_user -d agentops_db --no-owner < "${BACKUP_FILE}"

# 4. Restore n8n_db
docker compose -p agentops exec -T postgres \
  pg_restore -U n8n_user -d n8n_db --no-owner < "backups/postgres/n8n_db_*.dump"
```

---

## 4. Redis Persistence & Backup Procedures

Redis is configured with Append-Only File (`--appendonly yes`) mode for durability.

### Triggering a Point-in-Time Snapshot
```bash
# 1. Instruct Redis to perform a background save (RDB)
docker compose -p agentops exec redis redis-cli bgsave

# 2. Check that the save completed successfully
docker compose -p agentops exec redis redis-cli lastsave

# 3. Copy dump.rdb from the container to local backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker cp agentops_redis:/data/dump.rdb "backups/redis/dump_${TIMESTAMP}.rdb"
```

### Restoring Redis State
1. Stop the Redis container:
   ```bash
   docker compose -p agentops stop redis
   ```
2. Copy the backup RDB file into the volume directory:
   ```bash
   docker cp "backups/redis/dump_${TIMESTAMP}.rdb" agentops_redis:/data/dump.rdb
   ```
3. Restart Redis:
   ```bash
   docker compose -p agentops start redis
   ```

---

## 5. n8n Volume & Encryption Key Management

### Backup n8n Workflow Data Volume
n8n stores custom nodes, binary workflow cache, and local files in `/home/node/.n8n`.
```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create a compressed tarball directly from the volume container
docker run --rm \
  --volumes-from agentops_n8n \
  -v "$(pwd)/backups/n8n:/backup" \
  alpine tar -czf "/backup/n8n_data_${TIMESTAMP}.tar.gz" -C /home/node/.n8n .
```

### Encryption Key Recovery Policy
> [!IMPORTANT]
> The encryption key stored in `.env` under `N8N_ENCRYPTION_KEY` MUST be backed up to a secure password manager or secrets vault.
> 
> When restoring an n8n backup on a new machine:
> 1. Set `N8N_ENCRYPTION_KEY` in `.env` to the exact key used when the backup was taken.
> 2. Restore `n8n_db` in PostgreSQL.
> 3. Restore the `n8n_data` volume tarball:
>    ```bash
>    docker run --rm \
>      --volumes-from agentops_n8n \
>      -v "$(pwd)/backups/n8n:/backup" \
>      alpine sh -c "cd /home/node/.n8n && tar -xzf /backup/n8n_data_${TIMESTAMP}.tar.gz"
>    ```

---

## 6. Safe Reset Procedure (Non-Destructive vs. Destructive)

During testing, developers frequently need to clear stuck jobs or test pristine initial states. Follow this decision matrix to prevent accidental data loss.

### Option A: Clean Restart (Non-Destructive - Recommended)
Stops containers and clears volatile memory without removing databases or saved runs:
```bash
docker compose -p agentops restart
```

### Option B: Redis Queue Flush Only (Safe Job Reset)
Clears pending Celery broker messages without touching historical run data:
```bash
docker compose -p agentops exec redis redis-cli -n 1 flushdb
docker compose -p agentops exec redis redis-cli -n 2 flushdb
```

### Option C: Complete Volume Reset (Destructive - Requires Pre-Wipe Backup)

> [!WARNING]
> This permanently erases all PostgreSQL databases, Redis queues, and n8n configurations.
> Always take a snapshot backup before executing a volume reset!

```bash
# 1. Take snapshot backup first
mkdir -p backups/pre-reset
docker compose -p agentops exec -T postgres \
  pg_dump -U agentops_user -d agentops_db -Fc -Z 9 \
  > "backups/pre-reset/agentops_db_prereset.dump"

# 2. Stop services and remove named volumes
docker compose -p agentops down -v

# 3. Bring services back up with clean volumes
docker compose -p agentops up -d
```

### Forbidden Operations
- **Do NOT run** `docker system prune -a` (wipes images, caches, and sibling containers across the machine).
- **Do NOT run** `killall` or `pkill` commands on the host.
