from fastapi.testclient import TestClient
from main import app
import os

client = TestClient(app)


def test_health_all():
    # Ensure env variables exist for default checks
    os.environ.setdefault("DATABASE_URL", "postgres://user:pass@localhost:5432/forge")
    os.environ.setdefault("ANTHROPIC_API_KEY", "testkey")
    os.environ.setdefault("OPENAI_API_KEY", "testkey")

    # Alternative: set env vars so a supabase URL is set; otherwise the DB check returns skipped
    os.environ.setdefault("DATABASE_URL", "postgres://user:pass@localhost:5432/forge")
    # Simulate a chroma file
    os.environ.setdefault("CHROMA_DB_PATH", "./chroma_db/chroma.sqlite3")

    resp = client.get("/health/all")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "checks" in data
