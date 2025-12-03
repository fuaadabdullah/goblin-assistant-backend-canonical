#!/usr/bin/env python3
"""Test Silliconflow adapter"""

import asyncio
import re
from providers.silliconflow_adapter import SilliconflowAdapter


def load_env_direct():
    """Load .env file directly without using os.getenv()"""
    keys = {}
    with open(".env", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                match = re.match(r"([A-Z_]+)=(.*)", line)
                if match:
                    key, value = match.groups()
                    keys[key] = value
    return keys


async def test_silliconflow():
    """Test Silliconflow adapter."""
    env_keys = load_env_direct()
    api_key = env_keys.get("SILLICONFLOW_API_KEY", "")

    if not api_key or len(api_key) < 20:
        print("❌ SILLICONFLOW_API_KEY not found or invalid")
        return

    print(f"✅ API Key loaded: {len(api_key)} chars")
    print(f"🧪 Testing Silliconflow adapter...\n")

    adapter = SilliconflowAdapter(api_key=api_key, base_url=None)

    # Test health check
    print("1️⃣ Health Check...")
    health = await adapter.health_check()
    if health.get("healthy"):
        print(f"   ✅ Healthy (response time: {health.get('response_time_ms')}ms)")
        print(f"   📊 Available models: {health.get('available_models', 0)}")
    else:
        print(f"   ❌ Unhealthy: {health.get('error', 'Unknown error')}")

    # Test list models
    print("\n2️⃣ List Models...")
    models = await adapter.list_models()
    print(f"   📋 Found {len(models)} models")
    if models:
        print(f"   Sample models:")
        for model in models[:3]:
            print(f"      - {model['name']} ({model['id']})")

    # Test completion
    print("\n3️⃣ Test Completion...")
    result = await adapter.test_completion(
        model="Qwen/Qwen2.5-7B-Instruct", max_tokens=50
    )
    if result.get("success"):
        print(f"   ✅ Success (response time: {result.get('response_time_ms')}ms)")
        print(f"   🔢 Tokens used: {result.get('tokens_used', 'N/A')}")
    else:
        error = result.get("error", "Unknown error")
        if len(error) > 60:
            error = error[:60] + "..."
        print(f"   ❌ Failed: {error}")

    print("\n" + "=" * 60)
    print("✅ Silliconflow adapter test complete!")


if __name__ == "__main__":
    asyncio.run(test_silliconflow())
