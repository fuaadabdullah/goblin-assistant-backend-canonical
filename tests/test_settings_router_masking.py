from fastapi.testclient import TestClient
from main import app
import os

client = TestClient(app)


def test_settings_mask_api_keys():
    # Ensure env variables exist for default checks
    os.environ.setdefault("OPENAI_API_KEY", "sk-test-openai")
    os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-anthropic")
    os.environ.setdefault("GROQ_API_KEY", "sk-test-groq")

    resp = client.get("/settings/")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    for p in data["providers"]:
        # API keys must not be returned to caller
        assert p.get("api_key") is None

