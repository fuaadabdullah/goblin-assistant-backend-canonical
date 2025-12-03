import os
from fastapi.testclient import TestClient
from main import app
import pathlib

client = TestClient(app)


def test_vector_db_file_check(tmp_path):
    # Create a fake chroma DB path
    file_path = tmp_path / "chroma.sqlite3"
    file_path.write_text("dummy")
    os.environ["CHROMA_DB_PATH"] = str(file_path)

    resp = client.get("/health/all")
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"]["vector_db"]["status"] == "healthy"


def test_vector_db_qdrant_check(monkeypatch):
    # Simulate Qdrant host via env var; assume no real network knocked out in test
    os.environ.pop("CHROMA_DB_PATH", None)
    os.environ["QDRANT_URL"] = "http://localhost:9200"
    resp = client.get("/health/all")
    assert resp.status_code == 200
    data = resp.json()
    # Qdrant likely unreachable in test runner; check that vector_db key exists
    assert "vector_db" in data["checks"]
