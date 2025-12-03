# 🚀 Production Database Setup - Quick Reference

## Status: Ready to Execute

### What You Have Now

✅ **Supabase PostgreSQL**: Project `dhxoowakvmobjxsffpst` ready
✅ **Alembic Migrations**: Initial migration created (14 tables)
✅ **Setup Scripts**: Interactive tools created
✅ **Connection Pooling**: Production-ready configuration

---

## 🎯 Execute Now (3 Steps)

### Step 1: Interactive Setup (5 min)

```bash
cd /Users/fuaadabdullah/ForgeMonorepo/apps/goblin-assistant/backend
source venv/bin/activate
python3 setup_production.py
```

**What it does:**
- Guides you to get Supabase connection string
- Helps configure Upstash Redis (optional)
- Updates .env automatically

### Step 2: Test Connections (1 min)

```bash
python3 test_db_connection.py
```

**Expected output:**
```
✅ PostgreSQL Connection Successful!
✅ Redis Connection Successful! (if configured)
```

### Step 3: Run Migrations (2 min)

```bash
alembic upgrade head
```

**Expected output:**
```
INFO  [alembic] Running upgrade  -> 0ae54fa82ef0, Initial schema
```

**Verify:**
```bash
python3 -c "
from database import engine
from sqlalchemy import inspect
tables = inspect(engine).get_table_names()
print(f'✅ Created {len(tables)} tables')
"
```

---

## 📋 What You'll Need

### For PostgreSQL (Supabase)
1. Go to: https://supabase.com/dashboard/project/dhxoowakvmobjxsffpst/settings/database
2. Get database password (or reset it)
3. Copy "Connection pooling" string (port 6543)
4. Format: `postgresql://postgres.dhxoowakvmobjxsffpst:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres`

### For Redis (Upstash) - Optional
1. Go to: https://console.upstash.com
2. Create database (free tier available)
3. Get: endpoint, port (6379), password
4. Set SSL to `true`

---

## 🆘 If Something Goes Wrong

### Script not found
```bash
# Make sure you're in the right directory
cd /Users/fuaadabdullah/ForgeMonorepo/apps/goblin-assistant/backend
ls -la setup_production.py  # Should show the file
```

### Connection fails
```bash
# Check your .env file
cat .env | grep DATABASE_URL
cat .env | grep REDIS_

# Test manually
python3 test_db_connection.py
```

### Migration fails
```bash
# Check current migration state
alembic current

# If tables exist already
alembic stamp head

# Try again
alembic upgrade head
```

---

## ✅ Success Checklist

- [ ] Ran `setup_production.py` successfully
- [ ] Updated DATABASE_URL in .env
- [ ] Configured Redis (or skipped intentionally)
- [ ] Ran `test_db_connection.py` - all green
- [ ] Ran `alembic upgrade head` - no errors
- [ ] Verified 14 tables created

---

## 📚 Documentation

| File | Purpose |
|------|---------|
| `SETUP_GUIDE.md` | Complete manual instructions |
| `setup_production.py` | Interactive setup script |
| `test_db_connection.py` | Connection verification |
| `POSTGRESQL_MIGRATION.md` | Detailed migration guide |

---

## 🎉 After Setup

Your production database will be ready with:
- ✅ 14 tables created in PostgreSQL
- ✅ Connection pooling configured (20+40 connections)
- ✅ Redis for passkey challenges (if configured)
- ✅ All models migrated from SQLite schema

**Next:** Deploy to production!

---

**Time Required:** 10-15 minutes
**Difficulty:** Easy (fully guided)
**Support:** Run `python3 setup_production.py` for interactive help
