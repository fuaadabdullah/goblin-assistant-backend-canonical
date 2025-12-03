"""
Encryption service for securing API keys and sensitive data.
"""

import os
from typing import Optional
from cryptography.fernet import Fernet


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""

    def __init__(self, key: Optional[str] = None):
        """Initialize encryption service.

        Args:
            key: Base64-encoded encryption key. If None, uses ROUTING_ENCRYPTION_KEY env var.
        """
        if key is None:
            key = os.getenv("ROUTING_ENCRYPTION_KEY")
            if not key:
                raise ValueError(
                    "ROUTING_ENCRYPTION_KEY environment variable must be set"
                )

        self.cipher = Fernet(key.encode())

    def encrypt(self, data: str) -> str:
        """Encrypt a string.

        Args:
            data: String to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt a string.

        Args:
            encrypted_data: Base64-encoded encrypted string

        Returns:
            Decrypted string
        """
        return self.cipher.decrypt(encrypted_data.encode()).decode()
