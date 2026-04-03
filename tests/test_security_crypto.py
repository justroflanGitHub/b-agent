"""Tests for browser_agent.security.crypto — AES-256-GCM encryption utilities."""

import pytest
from browser_agent.security.crypto import CryptoEngine, EncryptedBlob


class TestEncryptedBlob:
    """Tests for EncryptedBlob serialization."""

    def test_to_dict_and_from_dict_roundtrip(self):
        blob = EncryptedBlob(
            ciphertext=b"encrypted_data_here",
            iv=b"\x00" * 12,
            tag=b"\x01" * 16,
            version=1,
        )
        d = blob.to_dict()
        restored = EncryptedBlob.from_dict(d)
        assert restored.ciphertext == blob.ciphertext
        assert restored.iv == blob.iv
        assert restored.tag == blob.tag
        assert restored.version == blob.version

    def test_to_json_and_from_json_roundtrip(self):
        blob = EncryptedBlob(
            ciphertext=b"\xff" * 32,
            iv=b"\xaa" * 12,
            tag=b"\xbb" * 16,
            version=2,
        )
        json_str = blob.to_json()
        restored = EncryptedBlob.from_json(json_str)
        assert restored.ciphertext == blob.ciphertext
        assert restored.iv == blob.iv
        assert restored.tag == blob.tag
        assert restored.version == 2

    def test_default_algorithm(self):
        blob = EncryptedBlob(ciphertext=b"x", iv=b"\x00" * 12, tag=b"\x00" * 16)
        assert blob.algorithm == "AES-256-GCM"


class TestCryptoEngine:
    """Tests for CryptoEngine encryption/decryption."""

    @pytest.fixture
    def crypto(self):
        return CryptoEngine(master_key=b'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!!')

    def test_invalid_key_length(self):
        with pytest.raises(ValueError, match="32 bytes"):
            CryptoEngine(master_key=b"short")

    def test_encrypt_decrypt_roundtrip(self, crypto):
        plaintext = "Hello, World!"
        blob = crypto.encrypt(plaintext)
        assert crypto.decrypt(blob) == plaintext

    def test_encrypt_decrypt_empty_string(self, crypto):
        blob = crypto.encrypt("")
        assert crypto.decrypt(blob) == ""

    def test_encrypt_decrypt_unicode(self, crypto):
        plaintext = "Привет мир 🌍 日本語テスト"
        blob = crypto.encrypt(plaintext)
        assert crypto.decrypt(blob) == plaintext

    def test_encrypt_decrypt_long_text(self, crypto):
        plaintext = "A" * 100_000
        blob = crypto.encrypt(plaintext)
        assert crypto.decrypt(blob) == plaintext

    def test_encrypt_produces_different_ciphertext(self, crypto):
        """Same plaintext encrypted twice should produce different ciphertext (random IV)."""
        blob1 = crypto.encrypt("same text")
        blob2 = crypto.encrypt("same text")
        assert blob1.ciphertext != blob2.ciphertext
        assert blob1.iv != blob2.iv

    def test_decrypt_with_wrong_key_fails(self, crypto):
        blob = crypto.encrypt("secret")
        wrong_crypto = CryptoEngine(master_key=b'cccccccccccccccccccccccccccccc!!')
        with pytest.raises(Exception):
            wrong_crypto.decrypt(blob)

    def test_tampered_ciphertext_fails(self, crypto):
        blob = crypto.encrypt("secret")
        tampered = EncryptedBlob(
            ciphertext=b"\x00" * len(blob.ciphertext),
            iv=blob.iv,
            tag=blob.tag,
        )
        with pytest.raises(Exception):
            crypto.decrypt(tampered)

    def test_generate_key_is_32_bytes(self):
        key = CryptoEngine.generate_key()
        assert len(key) == 32

    def test_generate_key_is_random(self):
        key1 = CryptoEngine.generate_key()
        key2 = CryptoEngine.generate_key()
        assert key1 != key2

    def test_key_from_password(self):
        key, salt = CryptoEngine.key_from_password("mypassword")
        assert len(key) == 32
        assert len(salt) == 16

    def test_key_from_password_deterministic(self):
        salt = b"\x01" * 16
        key1, _ = CryptoEngine.key_from_password("pass", salt)
        key2, _ = CryptoEngine.key_from_password("pass", salt)
        assert key1 == key2

    def test_key_from_password_different_salts(self):
        key1, _ = CryptoEngine.key_from_password("pass", b"\x01" * 16)
        key2, _ = CryptoEngine.key_from_password("pass", b"\x02" * 16)
        assert key1 != key2


class TestKeyDerivation:
    """Tests for tenant-scoped key derivation."""

    @pytest.fixture
    def crypto(self):
        return CryptoEngine(master_key=b'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!!')

    def test_derive_key_is_32_bytes(self, crypto):
        derived = crypto.derive_key("tenant_1")
        assert len(derived) == 32

    def test_derive_key_different_contexts(self, crypto):
        key1 = crypto.derive_key("tenant_1")
        key2 = crypto.derive_key("tenant_2")
        assert key1 != key2

    def test_derive_key_deterministic(self, crypto):
        key1 = crypto.derive_key("tenant_1")
        key2 = crypto.derive_key("tenant_1")
        assert key1 == key2

    def test_derive_child_engine(self, crypto):
        child = crypto.derive_child_engine("tenant_1")
        assert len(child._master_key) == 32
        assert child._master_key != crypto._master_key

    def test_tenant_isolation(self, crypto):
        """Different tenants should not be able to decrypt each other's data."""
        child1 = crypto.derive_child_engine("tenant_1")
        child2 = crypto.derive_child_engine("tenant_2")

        blob = child1.encrypt("tenant_1_secret")
        with pytest.raises(Exception):
            child2.decrypt(blob)


class TestKeyRotation:
    """Tests for master key rotation."""

    def test_rotate_key(self):
        old_key = b'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!!'
        new_key = b'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb!!'
        old_crypto = CryptoEngine(old_key)
        new_crypto = CryptoEngine(new_key)

        blobs = [old_crypto.encrypt(f"secret_{i}") for i in range(5)]
        rotated = old_crypto.rotate_key(new_key, blobs)

        assert len(rotated) == len(blobs)
        for blob, original in zip(rotated, blobs):
            assert blob.version == original.version + 1
            # New crypto can decrypt
            assert new_crypto.decrypt(blob) is not None

        # Verify all secrets are correct
        for i, blob in enumerate(rotated):
            assert new_crypto.decrypt(blob) == f"secret_{i}"
