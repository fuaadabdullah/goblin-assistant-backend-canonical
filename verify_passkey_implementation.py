#!/usr/bin/env python3
"""
Quick verification script for WebAuthn passkey implementation.
Tests the challenge store and verifies configuration.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))


def test_imports():
    """Test that all required modules can be imported"""
    print("✓ Testing imports...")
    try:
        from auth.challenge_store import (
            ChallengeStore,
            InMemoryChallengeStore,
            RedisChallengeStore,
            get_challenge_store_instance,
        )
        from auth.passkeys import WebAuthnPasskey

        print("  ✅ All imports successful")
        return True
    except Exception as e:
        print(f"  ❌ Import error: {e}")
        return False


async def test_challenge_store():
    """Test challenge store operations"""
    print("\n✓ Testing InMemoryChallengeStore...")
    try:
        from auth.challenge_store import InMemoryChallengeStore

        store = InMemoryChallengeStore()

        # Test set and get
        await store.set_challenge(
            "test@example.com", "test_challenge_123", ttl_minutes=5
        )
        challenge = await store.get_challenge("test@example.com")
        assert challenge == "test_challenge_123", "Challenge mismatch"
        print("  ✅ Set and get challenge")

        # Test delete
        deleted = await store.delete_challenge("test@example.com")
        assert deleted == True, "Delete failed"
        challenge = await store.get_challenge("test@example.com")
        assert challenge is None, "Challenge not deleted"
        print("  ✅ Delete challenge")

        # Test expiration
        await store.set_challenge("expire@example.com", "test", ttl_minutes=0)
        import asyncio

        await asyncio.sleep(0.1)
        challenge = await store.get_challenge("expire@example.com")
        assert challenge is None, "Expired challenge not removed"
        print("  ✅ Challenge expiration")

        # Test cleanup
        await store.set_challenge("test1@example.com", "c1", ttl_minutes=0)
        await store.set_challenge("test2@example.com", "c2", ttl_minutes=5)
        await asyncio.sleep(0.1)
        count = await store.cleanup_expired()
        assert count == 1, f"Cleanup count mismatch: {count}"
        print("  ✅ Cleanup expired challenges")

        print("  ✅ All InMemoryChallengeStore tests passed")
        return True
    except Exception as e:
        print(f"  ❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_webauthn_passkey():
    """Test WebAuthn passkey utilities"""
    print("\n✓ Testing WebAuthnPasskey...")
    try:
        from auth.passkeys import WebAuthnPasskey

        # Test challenge generation
        challenge = WebAuthnPasskey.generate_challenge()
        assert len(challenge) >= 32, "Challenge too short"
        print(f"  ✅ Generated challenge: {challenge[:20]}...")

        # Test base64url encoding/decoding
        test_data = b"Hello, World!"
        encoded = WebAuthnPasskey.encode_base64url(test_data)
        decoded = WebAuthnPasskey.decode_base64url(encoded)
        assert decoded == test_data, "Encode/decode mismatch"
        print("  ✅ Base64url encode/decode")

        print("  ✅ All WebAuthnPasskey tests passed")
        return True
    except Exception as e:
        print(f"  ❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_environment():
    """Check environment configuration"""
    print("\n✓ Checking environment configuration...")

    required_vars = {
        "FRONTEND_URL": "Frontend URL for origin validation",
        "JWT_SECRET_KEY": "JWT secret key for token signing",
    }

    optional_vars = {
        "USE_REDIS_CHALLENGES": "Enable Redis for challenge storage (default: false)",
        "REDIS_HOST": "Redis host (default: localhost)",
        "REDIS_PORT": "Redis port (default: 6379)",
    }

    all_good = True

    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "KEY" in var or "SECRET" in var:
                display_value = (
                    f"{value[:10]}...{value[-5:]}" if len(value) > 15 else "***"
                )
            else:
                display_value = value
            print(f"  ✅ {var} = {display_value}")
        else:
            print(f"  ⚠️  {var} not set - {description}")
            all_good = False

    for var, description in optional_vars.items():
        value = os.getenv(var)
        if value:
            print(f"  ℹ️  {var} = {value}")
        else:
            print(f"  ℹ️  {var} not set (optional) - {description}")

    return all_good


async def main():
    """Run all verification tests"""
    print("=" * 60)
    print("WebAuthn Passkey Implementation Verification")
    print("=" * 60)

    results = []

    # Test imports
    results.append(("Imports", test_imports()))

    # Test challenge store
    results.append(("Challenge Store", await test_challenge_store()))

    # Test WebAuthn utilities
    results.append(("WebAuthn Utilities", test_webauthn_passkey()))

    # Check environment
    results.append(("Environment", check_environment()))

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n🎉 All verification tests passed!")
        print("✅ WebAuthn passkey implementation is working correctly")
        print("\n📝 Next steps:")
        print("  1. Set FRONTEND_URL in .env to your frontend domain")
        print("  2. For production, set USE_REDIS_CHALLENGES=true")
        print("  3. Run the full test suite: pytest auth/tests/test_passkey_e2e.py -v")
        print("  4. Start the server: uvicorn main:app --reload")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Run tests
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
