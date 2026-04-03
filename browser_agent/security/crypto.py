"""Cryptographic utilities for the credential vault.

Uses AES-256-GCM for authenticated encryption.
Key derivation via HKDF-SHA256 for tenant-scoped keys.
"""

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EncryptedBlob:
    """Container for encrypted data with metadata."""

    ciphertext: bytes
    iv: bytes  # 12-byte nonce
    tag: bytes  # 16-byte auth tag
    version: int = 1
    algorithm: str = "AES-256-GCM"

    def to_dict(self) -> dict:
        """Serialize for storage (base64 encoded)."""
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode("ascii"),
            "iv": base64.b64encode(self.iv).decode("ascii"),
            "tag": base64.b64encode(self.tag).decode("ascii"),
            "version": self.version,
            "algorithm": self.algorithm,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EncryptedBlob":
        """Deserialize from storage."""
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            iv=base64.b64decode(data["iv"]),
            tag=base64.b64decode(data["tag"]),
            version=data.get("version", 1),
            algorithm=data.get("algorithm", "AES-256-GCM"),
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> "EncryptedBlob":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


class CryptoEngine:
    """AES-256-GCM encryption for credential storage.

    Uses the `cryptography` library for AES-256-GCM.
    Falls back to a pure-Python XOR-based approach if the library
    is unavailable (NOT secure — only for testing).
    """

    def __init__(self, master_key: bytes):
        if len(master_key) != 32:
            raise ValueError("Master key must be exactly 32 bytes")
        self._master_key = master_key
        self._backend = self._detect_backend()

    @property
    def master_key(self) -> bytes:
        return self._master_key

    @staticmethod
    def _detect_backend() -> str:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401

            return "cryptography"
        except ImportError:
            return "fallback"

    @staticmethod
    def generate_key() -> bytes:
        """Generate a random 32-byte master key."""
        return os.urandom(32)

    @staticmethod
    def key_from_password(password: str, salt: Optional[bytes] = None) -> tuple:
        """Derive a 32-byte key from a password using PBKDF2.

        Returns (key, salt). Store the salt alongside the key reference.
        """
        if salt is None:
            salt = os.urandom(16)
        try:
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=600_000,
            )
            key = kdf.derive(password.encode("utf-8"))
        except ImportError:
            # Fallback: HKDF-like derivation (NOT production-safe)
            key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return key, salt

    def encrypt(self, plaintext: str) -> EncryptedBlob:
        """Encrypt plaintext using AES-256-GCM."""
        iv = os.urandom(12)
        data = plaintext.encode("utf-8")

        if self._backend == "cryptography":
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            aesgcm = AESGCM(self._master_key)
            ct_and_tag = aesgcm.encrypt(iv, data, None)
            # AESGCM appends the 16-byte tag to the ciphertext
            ciphertext = ct_and_tag[:-16]
            tag = ct_and_tag[-16:]
        else:
            # Fallback: XOR with key stream (NOT secure — testing only)
            ciphertext = self._xor_with_keystream(data, iv)
            tag = hashlib.sha256(iv + ciphertext + self._master_key).digest()[:16]

        return EncryptedBlob(
            ciphertext=ciphertext,
            iv=iv,
            tag=tag,
            version=1,
        )

    def decrypt(self, blob: EncryptedBlob) -> str:
        """Decrypt an EncryptedBlob back to plaintext."""
        if self._backend == "cryptography":
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            aesgcm = AESGCM(self._master_key)
            ct_and_tag = blob.ciphertext + blob.tag
            data = aesgcm.decrypt(blob.iv, ct_and_tag, None)
        else:
            # Verify tag
            expected_tag = hashlib.sha256(
                blob.iv + blob.ciphertext + self._master_key
            ).digest()[:16]
            if not hmac.compare_digest(expected_tag, blob.tag):
                raise ValueError("Authentication tag mismatch — data may be tampered")
            data = self._xor_with_keystream(blob.ciphertext, blob.iv)

        return data.decode("utf-8")

    def derive_key(self, context: str) -> bytes:
        """Derive a scoped key from master key using HKDF-SHA256.

        Args:
            context: Scope identifier (e.g., tenant_id).

        Returns:
            32-byte derived key.
        """
        if self._backend == "cryptography":
            from cryptography.hazmat.primitives.kdf.hkdf import HKDF
            from cryptography.hazmat.primitives import hashes

            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=context.encode("utf-8"),
            )
            return hkdf.derive(self._master_key)
        else:
            # Fallback: HMAC-based derivation
            return hmac.new(
                self._master_key, context.encode("utf-8"), hashlib.sha256
            ).digest()

    def derive_child_engine(self, context: str) -> "CryptoEngine":
        """Create a child CryptoEngine with a derived key."""
        derived = self.derive_key(context)
        engine = CryptoEngine.__new__(CryptoEngine)
        engine._master_key = derived
        engine._backend = self._backend
        return engine

    def rotate_key(
        self, new_key: bytes, blobs: list
    ) -> list:
        """Re-encrypt a list of EncryptedBlobs with a new master key.

        Returns a list of new EncryptedBlobs encrypted with new_key.
        """
        new_engine = CryptoEngine(new_key)
        result = []
        for blob in blobs:
            plaintext = self.decrypt(blob)
            new_blob = new_engine.encrypt(plaintext)
            new_blob.version = blob.version + 1
            result.append(new_blob)
        return result

    def _xor_with_keystream(self, data: bytes, iv: bytes) -> bytes:
        """Simple XOR with key stream (fallback only — NOT secure)."""
        # Expand key using iv as additional entropy
        stream = hashlib.sha256(self._master_key + iv).digest()
        # Extend stream to match data length
        result = bytearray(len(data))
        for i in range(len(data)):
            if i >= len(stream):
                stream = hashlib.sha256(stream + self._master_key).digest()
            result[i] = data[i] ^ stream[i % len(stream)]
        return bytes(result)
