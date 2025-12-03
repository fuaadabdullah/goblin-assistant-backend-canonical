"""
End-to-End WebAuthn Passkey Integration Tests

This test suite validates the complete passkey authentication flow including:
- Challenge generation
- Passkey registration
- Passkey authentication
- Challenge expiration
- Security validations
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import secrets
import base64
import json
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
import hashlib

# Import app components
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from main import app
from auth.passkeys import WebAuthnPasskey
from database import get_db, engine
from models import Base, User

# Test client
client = TestClient(app)


@pytest.fixture(scope="function")
def setup_database():
    """Create test database tables"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def generate_test_passkey_data(challenge: str):
    """
    Generate realistic passkey authentication data for testing.

    This simulates what a WebAuthn client (browser) would generate:
    - EC private/public key pair
    - Authenticator data
    - Client data JSON
    - Signature over authenticator_data + SHA256(client_data_json)
    """
    # Generate EC key pair (ES256 - P-256 curve)
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key = private_key.public_key()

    # Extract public key coordinates for COSE format
    public_numbers = public_key.public_numbers()
    x = public_numbers.x.to_bytes(32, byteorder="big")
    y = public_numbers.y.to_bytes(32, byteorder="big")

    # COSE public key format (uncompressed point)
    # 0x04 prefix + x + y coordinates
    cose_public_key = b"\x04" + x + y
    cose_public_key_b64 = WebAuthnPasskey.encode_base64url(cose_public_key)

    # Generate credential ID
    credential_id = secrets.token_bytes(32)
    credential_id_b64 = WebAuthnPasskey.encode_base64url(credential_id)

    # Create authenticator data
    # Format: RP ID hash (32) + flags (1) + counter (4)
    rp_id_hash = hashlib.sha256(b"localhost").digest()
    flags = bytes([0x05])  # UP (user present) + UV (user verified)
    counter = (1).to_bytes(4, byteorder="big")
    authenticator_data = rp_id_hash + flags + counter
    authenticator_data_b64 = WebAuthnPasskey.encode_base64url(authenticator_data)

    # Create client data JSON
    client_data = {
        "type": "webauthn.get",
        "challenge": challenge,
        "origin": os.getenv("FRONTEND_URL", "http://localhost:3000"),
        "crossOrigin": False,
    }
    client_data_json = json.dumps(client_data).encode("utf-8")
    client_data_json_b64 = WebAuthnPasskey.encode_base64url(client_data_json)

    # Create signature
    # Sign over: authenticator_data + SHA256(client_data_json)
    client_data_hash = hashlib.sha256(client_data_json).digest()
    signed_data = authenticator_data + client_data_hash

    signature = private_key.sign(signed_data, ec.ECDSA(hashes.SHA256()))
    signature_b64 = WebAuthnPasskey.encode_base64url(signature)

    return {
        "credential_id": credential_id_b64,
        "public_key": cose_public_key_b64,
        "authenticator_data": authenticator_data_b64,
        "client_data_json": client_data_json_b64,
        "signature": signature_b64,
        "private_key": private_key,  # Keep for potential future tests
        "public_key_obj": public_key,
    }


class TestPasskeyE2E:
    """End-to-end passkey authentication tests"""

    def test_complete_passkey_flow(self, setup_database):
        """Test the complete passkey registration and authentication flow"""
        test_email = "test@example.com"

        # Step 1: Register a user first (required for passkey)
        register_response = client.post(
            "/auth/register",
            json={"email": test_email, "password": "Test123!@#", "name": "Test User"},
        )
        assert register_response.status_code in [200, 201], (
            f"Registration failed: {register_response.text}"
        )

        # Step 2: Request a challenge for registration
        challenge_response = client.post(
            "/auth/passkey/challenge", json={"email": test_email}
        )
        assert challenge_response.status_code == 200
        challenge_data = challenge_response.json()
        assert "challenge" in challenge_data
        challenge = challenge_data["challenge"]

        # Step 3: Generate passkey data
        passkey_data = generate_test_passkey_data(challenge)

        # Step 4: Register the passkey
        register_passkey_response = client.post(
            "/auth/passkey/register",
            json={
                "email": test_email,
                "credential_id": passkey_data["credential_id"],
                "public_key": passkey_data["public_key"],
            },
        )
        assert register_passkey_response.status_code == 200
        assert "successfully" in register_passkey_response.json()["message"].lower()

        # Step 5: Request a new challenge for authentication
        auth_challenge_response = client.post(
            "/auth/passkey/challenge", json={"email": test_email}
        )
        assert auth_challenge_response.status_code == 200
        auth_challenge = auth_challenge_response.json()["challenge"]

        # Step 6: Generate authentication data with new challenge
        auth_data = generate_test_passkey_data(auth_challenge)
        # Use the same credential ID and public key from registration
        auth_data["credential_id"] = passkey_data["credential_id"]
        auth_data["public_key"] = passkey_data["public_key"]

        # Step 7: Authenticate with passkey
        auth_response = client.post(
            "/auth/passkey/auth",
            json={
                "email": test_email,
                "credential_id": auth_data["credential_id"],
                "authenticator_data": auth_data["authenticator_data"],
                "client_data_json": auth_data["client_data_json"],
                "signature": auth_data["signature"],
            },
        )
        assert auth_response.status_code == 200
        token_data = auth_response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["user"]["email"] == test_email

    def test_challenge_expiration(self, setup_database):
        """Test that expired challenges are rejected"""
        test_email = "expire@example.com"

        # Register user
        client.post(
            "/auth/register",
            json={"email": test_email, "password": "Test123!@#", "name": "Expire Test"},
        )

        # Request challenge
        challenge_response = client.post(
            "/auth/passkey/challenge", json={"email": test_email}
        )
        challenge = challenge_response.json()["challenge"]

        # Register passkey
        passkey_data = generate_test_passkey_data(challenge)
        client.post(
            "/auth/passkey/register",
            json={
                "email": test_email,
                "credential_id": passkey_data["credential_id"],
                "public_key": passkey_data["public_key"],
            },
        )

        # Request auth challenge
        auth_challenge_response = client.post(
            "/auth/passkey/challenge", json={"email": test_email}
        )
        auth_challenge = auth_challenge_response.json()["challenge"]

        # Manually expire the challenge (simulate time passing)
        # Access the challenge store directly
        from auth.router import challenge_store

        if test_email in challenge_store:
            challenge_store[test_email]["expires"] = datetime.utcnow() - timedelta(
                minutes=1
            )

        # Try to authenticate with expired challenge
        auth_data = generate_test_passkey_data(auth_challenge)
        auth_data["credential_id"] = passkey_data["credential_id"]

        auth_response = client.post(
            "/auth/passkey/auth",
            json={
                "email": test_email,
                "credential_id": auth_data["credential_id"],
                "authenticator_data": auth_data["authenticator_data"],
                "client_data_json": auth_data["client_data_json"],
                "signature": auth_data["signature"],
            },
        )
        assert auth_response.status_code == 401
        assert "expired" in auth_response.json()["detail"].lower()

    def test_challenge_one_time_use(self, setup_database):
        """Test that challenges can only be used once"""
        test_email = "onetime@example.com"

        # Register user
        client.post(
            "/auth/register",
            json={
                "email": test_email,
                "password": "Test123!@#",
                "name": "OneTime Test",
            },
        )

        # Request and register passkey
        challenge_response = client.post(
            "/auth/passkey/challenge", json={"email": test_email}
        )
        challenge = challenge_response.json()["challenge"]
        passkey_data = generate_test_passkey_data(challenge)

        client.post(
            "/auth/passkey/register",
            json={
                "email": test_email,
                "credential_id": passkey_data["credential_id"],
                "public_key": passkey_data["public_key"],
            },
        )

        # Request auth challenge
        auth_challenge_response = client.post(
            "/auth/passkey/challenge", json={"email": test_email}
        )
        auth_challenge = auth_challenge_response.json()["challenge"]
        auth_data = generate_test_passkey_data(auth_challenge)
        auth_data["credential_id"] = passkey_data["credential_id"]

        # First authentication should succeed
        first_auth = client.post(
            "/auth/passkey/auth",
            json={
                "email": test_email,
                "credential_id": auth_data["credential_id"],
                "authenticator_data": auth_data["authenticator_data"],
                "client_data_json": auth_data["client_data_json"],
                "signature": auth_data["signature"],
            },
        )
        assert first_auth.status_code == 200

        # Second authentication with same data should fail (challenge consumed)
        second_auth = client.post(
            "/auth/passkey/auth",
            json={
                "email": test_email,
                "credential_id": auth_data["credential_id"],
                "authenticator_data": auth_data["authenticator_data"],
                "client_data_json": auth_data["client_data_json"],
                "signature": auth_data["signature"],
            },
        )
        assert second_auth.status_code == 401
        assert "no challenge found" in second_auth.json()["detail"].lower()

    def test_invalid_credential_id(self, setup_database):
        """Test that invalid credential IDs are rejected"""
        test_email = "invalid@example.com"

        # Register user and passkey
        client.post(
            "/auth/register",
            json={
                "email": test_email,
                "password": "Test123!@#",
                "name": "Invalid Test",
            },
        )

        challenge_response = client.post(
            "/auth/passkey/challenge", json={"email": test_email}
        )
        challenge = challenge_response.json()["challenge"]
        passkey_data = generate_test_passkey_data(challenge)

        client.post(
            "/auth/passkey/register",
            json={
                "email": test_email,
                "credential_id": passkey_data["credential_id"],
                "public_key": passkey_data["public_key"],
            },
        )

        # Request auth challenge
        auth_challenge_response = client.post(
            "/auth/passkey/challenge", json={"email": test_email}
        )
        auth_challenge = auth_challenge_response.json()["challenge"]
        auth_data = generate_test_passkey_data(auth_challenge)

        # Use DIFFERENT credential ID (not the registered one)
        wrong_credential = WebAuthnPasskey.encode_base64url(secrets.token_bytes(32))

        auth_response = client.post(
            "/auth/passkey/auth",
            json={
                "email": test_email,
                "credential_id": wrong_credential,
                "authenticator_data": auth_data["authenticator_data"],
                "client_data_json": auth_data["client_data_json"],
                "signature": auth_data["signature"],
            },
        )
        assert auth_response.status_code == 401
        assert "invalid" in auth_response.json()["detail"].lower()

    def test_registration_validation(self, setup_database):
        """Test validation during passkey registration"""
        test_email = "validation@example.com"

        # Register user
        client.post(
            "/auth/register",
            json={
                "email": test_email,
                "password": "Test123!@#",
                "name": "Validation Test",
            },
        )

        # Test with invalid credential_id (too short)
        response = client.post(
            "/auth/passkey/register",
            json={
                "email": test_email,
                "credential_id": "short",
                "public_key": "also-short",
            },
        )
        assert response.status_code == 400

        # Test with invalid base64url
        response = client.post(
            "/auth/passkey/register",
            json={
                "email": test_email,
                "credential_id": "invalid!!!base64url!!!chars",
                "public_key": "also!!!invalid",
            },
        )
        assert response.status_code == 400


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
