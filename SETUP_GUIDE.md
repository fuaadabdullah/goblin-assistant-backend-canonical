# Quick Production Setup Guide

## Overview
You need to: (1) Get PostgreSQL connection from Supabase, (2) Set up Redis on Upstash, (3) Run migrations

---

## ✅ STEP 1: PostgreSQL (Supabase)

### Get Your Connection String

1. **Open Supabase Dashboard:**
   ```
   https://supabase.com/dashboard/project/dhxoowakvmobjxsffpst/settings/database
   ```

2. **Get/Reset Database Password:**
   - Scroll to "Database Password" section
   - Click "Reset Database Password" if needed
   - **SAVE THIS PASSWORD** - you'll need it!

3. **Get Connection String:**
   - Scroll to "Connection string" section
   - Click **"Connection pooling"** tab (port 6543)
   - Copy the string (looks like this):
     ```
     postgresql://postgres.dhxoowakvmobjxsffpst:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
     ```
   - Replace `[YOUR-PASSWORD]` with your actual password

### Update Your .env File

Open `.env` file and update this line:

```bash
# BEFORE (SQLite):
DATABASE_URL=sqlite:///./goblin_assistant.db

# AFTER (PostgreSQL):
DATABASE_URL=postgresql://postgres.dhxoowakvmobjxsffpst:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

**Or use this command:**
```bash
cd /Users/fuaadabdullah/ForgeMonorepo/apps/goblin-assistant/backend

# Create backup first
cp .env .env.backup

# Edit .env and replace the DATABASE_URL line
nano .env
# Or use your preferred editor: code .env, vim .env, etc.
```

---

## ✅ STEP 2: Redis (Upstash)

### Create Redis Database

1. **Go to Upstash:**
   ```
   https://console.upstash.com
   ```

2. **Sign In/Sign Up** (free tier available)

3. **Create Database:**
   - Click "Create Database"
   - Name: `goblin-assistant-redis`
   - Region: Choose closest to your backend
   - Type: Regional (cheaper) or Global (better latency)
   - Click "Create"

4. **Get Connection Details:**
   From the database dashboard, copy:
   - **Endpoint** (e.g., `example-12345.upstash.io`)
   - **Port** (usually `6379`)
   - **Password** (click "eye" icon to reveal)

### Update Your .env File

Update these lines in `.env`:

```bash
# Redis Configuration
USE_REDIS_CHALLENGES=true  # ← Change to true
REDIS_HOST=your-endpoint.upstash.io  # ← Your endpoint
REDIS_PORT=6379  # ← Usually 6379
REDIS_DB=0
REDIS_PASSWORD=your-redis-password  # ← Your password
REDIS_SSL=true  # ← Set to true for Upstash
```

---

## ✅ STEP 3: Run Migrations

Once DATABASE_URL is updated, run:

```bash
cd /Users/fuaadabdullah/ForgeMonorepo/apps/goblin-assistant/backend

# Activate virtual environment
source venv/bin/activate

# Test connection first
python3 -c "
from database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT version()'))
    print('✅ Connected to PostgreSQL!')
    print(f'Version: {result.fetchone()[0][:80]}')
"

# Run migrations (creates all tables)
alembic upgrade head
```

### Expected Output:
```
INFO  [alembic.runtime.migration] Context impl PostgreSQLImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0ae54fa82ef0, Initial schema with all models
```

---

## ✅ Verify Everything Works

```bash
# 1. Check database tables
python3 -c "
from database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f'✅ Created {len(tables)} tables:')
for table in sorted(tables):
    print(f'  - {table}')
"

# 2. Test Redis connection (if configured)
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()

if os.getenv('USE_REDIS_CHALLENGES') == 'true':
    import redis
    r = redis.Redis(
        host=os.getenv('REDIS_HOST'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        password=os.getenv('REDIS_PASSWORD'),
        ssl=os.getenv('REDIS_SSL', 'false').lower() == 'true'
    )
    r.ping()
    print('✅ Redis connection successful!')
else:
    print('⚠️  Redis not configured (using in-memory storage)')
"
```

---

## 🆘 Troubleshooting

### "Connection refused" or timeout
- Check if you're using the correct connection string
- Verify port is 6543 (connection pooling) not 5432 (direct)
- Check Supabase project is not paused
- Verify your IP is not blocked

### "Password authentication failed"
- Double-check your password
- Try resetting it in Supabase dashboard
- Make sure there are no extra spaces in .env

### "relation already exists"
If you see this error, your tables already exist. You can:
```bash
# Mark current state as baseline
alembic stamp head
```

### Redis connection fails
- Verify endpoint and password
- Check SSL is set to `true` for Upstash
- Test with: `redis-cli -h <host> -p 6379 -a <password> --tls PING`

---

## 📝 Quick Checklist

- [ ] Supabase project accessible
- [ ] Database password obtained
- [ ] CONNECTION_URL updated in `.env`
- [ ] Upstash Redis created
- [ ] Redis credentials updated in `.env`
- [ ] Virtual environment activated
- [ ] PostgreSQL connection tested
- [ ] Migrations run successfully (`alembic upgrade head`)
- [ ] Tables created (14 tables total)
- [ ] Redis connection tested

---

## 🎉 Done!

Your production database is ready! Next steps:
- Deploy backend to production
- Update production env vars with same values
- Test all endpoints

**Backup Reminder:** Your `.env.backup` file has your old SQLite config if you need to roll back.
