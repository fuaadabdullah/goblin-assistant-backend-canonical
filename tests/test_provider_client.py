import pytest
import respx
from httpx import Response
from providers.client import ProviderClient


@respx.mock
@pytest.mark.asyncio
async def test_provider_client_post_retries_success():
    base_url = "https://mockprovider.test"
    # Mock endpoint to return 429 twice, then 200
    route = respx.post(f"{base_url}/").mock(side_effect=[Response(429, json={"error":"rate limit"}), Response(429, json={"error":"rate limit"}), Response(200, json={"ok": True})])

    client = ProviderClient(base_url=base_url, api_key="test", timeout=1)

    resp = await client.post(path="", payload={"foo":"bar"}, retries=3, backoff=0.1)
    assert resp.get("ok") is True
