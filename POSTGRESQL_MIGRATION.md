# PostgreSQL Migration Guide

## Overview

This guide covers migrating the Goblin Assistant from SQLite (development) to PostgreSQL (production) using Alembic migrations.

## ✅ What's Been Set Up

### 1. Alembic Configuration
- ✅ Alembic initialized in `backend/alembic/`
- ✅ Initial migration generated with all models
- ✅ `env.py` configured to use DATABASE_URL from environment
- ✅ All models imported and registered

### 2. Database Connection Pooling
- ✅ Production-ready connection pool (20 base + 40 overflow)
- ✅ Pool timeout: 30 seconds
- ✅ Connection recycling: 1 hour
- ✅ Pre-ping enabled (detects stale connections)
- ✅ Query timeout: 30 seconds
- ✅ Connection timeout: 10 seconds

### 3. Environment Configuration
- ✅ `DATABASE_URL` support for both SQLite and PostgreSQL
- ✅ Configurable pool settings via environment variables
- ✅ Automatic detection of database type

## 🚀 Migration Steps

### Step 1: Set Up PostgreSQL Database

#### Option A: Supabase (Recommended)

You already have a Supabase project! Just get the direct PostgreSQL connection string:

```bash
# Go to Supabase Dashboard > Project Settings > Database
# Copy the "Connection string" under "Direct connection"
# It looks like: postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:5432/postgres

# Your Supabase project:
# Project: dhxoowakvmobjxsffpst
# Get password from Supabase dashboard
```

#### Option B: Local PostgreSQL

```bash
# Install PostgreSQL
# macOS:
brew install postgresql@15
brew services start postgresql@15

# Create database
createdb goblin_assistant

# Get connection string
DATABASE_URL=postgresql://localhost:5432/goblin_assistant
```

#### Option C: Managed PostgreSQL
- AWS RDS
- Google Cloud SQL
- Digital Ocean Managed Databases
- Render PostgreSQL

### Step 2: Update Environment Variables

**Update `.env` or `.env.production`:**

```bash
# Replace SQLite URL with PostgreSQL URL
DATABASE_URL=postgresql://postgres.dhxoowakvmobjxsffpst:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres

# Optional: Customize connection pool settings
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
```

### Step 3: Run Migrations

```bash
cd /Users/fuaadabdullah/ForgeMonorepo/apps/goblin-assistant/backend

# Activate virtual environment
source venv/bin/activate

# Check current database state
alembic current

# View migration history
alembic history

# Run migrations (creates all tables)
alembic upgrade head
```

### Step 4: Verify Migration

```bash
# Check that migration succeeded
alembic current
# Should show: 0ae54fa82ef0 (head)

# Test database connection
python3 -c "
from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('✅ Database connection successful')
    print(f'Database: {engine.url.database}')
    print(f'Host: {engine.url.host}')
"
```

### Step 5: Migrate Data (If Needed)

If you have existing data in SQLite that needs to be migrated:

```bash
# 1. Export SQLite data
python3 scripts/export_sqlite_data.py

# 2. Update DATABASE_URL to PostgreSQL

# 3. Run migrations
alembic upgrade head

# 4. Import data to PostgreSQL
python3 scripts/import_postgres_data.py
```

## 📊 Database Schema

### Tables Created by Migration

1. **users** - User accounts and authentication
2. **tasks** - Task execution records
3. **streams** - WebSocket stream sessions
4. **stream_chunks** - Individual stream chunks
5. **search_collections** - RAG search collections
6. **search_documents** - RAG documents
7. **providers** - AI provider configurations
8. **provider_credentials** - Encrypted API keys
9. **model_configs** - Model parameters
10. **global_settings** - Application settings
11. **routing_providers** - Routing provider registry
12. **provider_metrics** - Provider health metrics
13. **provider_policies** - Routing policies
14. **routing_requests** - Routing request logs

## 🔧 Common Migration Commands

```bash
# Create a new migration (after model changes)
alembic revision --autogenerate -m "Add new column"

# Upgrade to latest version
alembic upgrade head

# Downgrade one version
alembic downgrade -1

# Show current version
alembic current

# Show migration history
alembic history --verbose

# Upgrade to specific version
alembic upgrade <revision>

# Reset to base (WARNING: drops all tables)
alembic downgrade base
```

## 🚨 Troubleshooting

### Connection Refused

```bash
# Check if PostgreSQL is running
pg_isready -h [host] -p 5432

# For Supabase, check if IP is allowlisted
# Go to Supabase Dashboard > Database > Connection pooler
```

### Password Authentication Failed

```bash
# Verify password in connection string
# Supabase: Get password from Database Settings
# Format: postgresql://postgres.[ref]:[PASSWORD]@host:5432/postgres
```

### SSL Required

```bash
# Add SSL mode to connection string
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
```

### Table Already Exists

```bash
# If tables were created manually, mark migration as done
alembic stamp head

# Or drop all tables and start fresh (CAUTION!)
# In Python:
from database import drop_tables
drop_tables()

# Then run migrations
alembic upgrade head
```

### Pool Timeout Errors

```bash
# Increase pool size
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=60

# Or increase timeout
DB_POOL_TIMEOUT=60
```

## 📈 Monitoring Connection Pool

Add health check endpoint to monitor pool:

```python
from fastapi import APIRouter
from database import engine

@router.get("/health/db-pool")
async def health_db_pool():
    """Check database connection pool status"""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in_connections": pool.checkedin(),
        "checked_out_connections": pool.checkedout(),
        "overflow_connections": pool.overflow(),
        "total_connections": pool.size() + pool.overflow()
    }
```

## 🔐 Security Best Practices

### 1. Row Level Security (Supabase)

```sql
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
-- ... repeat for all tables

-- Create policies
CREATE POLICY "Users can view own data"
  ON users FOR SELECT
  USING (auth.uid() = id::text);
```

### 2. Connection Security

```bash
# Always use SSL in production
DATABASE_URL=postgresql://...?sslmode=require

# For Supabase, use pooler connection (better performance)
# Use direct connection only for migrations
```

### 3. Credentials Management

```bash
# Never commit database passwords
# Use environment variables or secrets manager
# Rotate passwords every 90 days
```

## ✅ Post-Migration Checklist

- [ ] All tables created successfully
- [ ] Indexes created for all primary and foreign keys
- [ ] Connection pool configured properly
- [ ] Health checks passing
- [ ] Data migrated (if applicable)
- [ ] Backup strategy in place
- [ ] Monitoring configured
- [ ] SSL/TLS enabled
- [ ] RLS policies set up (Supabase)
- [ ] Old SQLite file backed up

## 🎯 Next Steps

1. **Test in staging** with production-like data
2. **Set up automated backups** (Supabase has automatic backups)
3. **Configure monitoring** (Datadog, Sentry, etc.)
4. **Load testing** to tune pool settings
5. **Document rollback procedure**

## 📚 References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- [Supabase Database Guide](https://supabase.com/docs/guides/database)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)

---

**Last Updated**: December 1, 2025
**Migration Status**: Ready to execute
**Estimated Time**: 5-10 minutes (depending on data volume)
