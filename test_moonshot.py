#!/usr/bin/env python3
"""Test Moonshot AI adapter"""

import asyncio
import re
from providers.moonshot_adapter import MoonshotAdapter


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


async def test_moonshot():
    """Test Moonshot AI adapter."""
    env_keys = load_env_direct()
    api_key = env_keys.get("MOONSHOT_API_KEY", "")

    if not api_key or len(api_key) < 20:
        print("❌ MOONSHOT_API_KEY not found or invalid")
        return

    print(f"✅ API Key loaded: {len(api_key)} chars")
    print("🧪 Testing Moonshot AI (Kimi) adapter...\n")

    adapter = MoonshotAdapter(api_key=api_key, base_url=None)

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
        print("   Sample models:")
        for model in models[:5]:
            print(f"      - {model['name']} ({model['id']})")
            print(f"        Context: {model['context_window']:,} tokens")

    # Test completion
    print("\n3️⃣ Test Completion...")
    result = await adapter.test_completion(model="moonshot-v1-8k", max_tokens=50)
    if result.get("success"):
        print(f"   ✅ Success (response time: {result.get('response_time_ms')}ms)")
        print(f"   🔢 Tokens used: {result.get('tokens_used', 'N/A')}")
    else:
        error = result.get("error", "Unknown error")
        if len(error) > 60:
            error = error[:60] + "..."
        print(f"   ❌ Failed: {error}")

    print("\n" + "=" * 60)
    print("✅ Moonshot AI adapter test complete!")


if __name__ == "__main__":
    asyncio.run(test_moonshot())
