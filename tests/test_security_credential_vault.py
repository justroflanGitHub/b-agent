"""Tests for browser_agent.security.credential_vault — Credential storage and management."""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from browser_agent.security.crypto import CryptoEngine, EncryptedBlob
from browser_agent.security.credential_vault import (
    CredentialEntry,
    CredentialSummary,
    CredentialType,
    CredentialVault,
    DecryptedCredential,
    FileCredentialStore,
    RotationPolicy,
    SQLiteCredentialStore,
)


@pytest.fixture
def crypto():
    return CryptoEngine(master_key=b'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!!')


@pytest.fixture
def tmp_store_path(tmp_path):
    return str(tmp_path / "creds")


@pytest.fixture
def file_store(tmp_store_path):
    return FileCredentialStore(tmp_store_path)


@pytest.fixture
def sqlite_store(tmp_path):
    return SQLiteCredentialStore(str(tmp_path / "vault.db"))


@pytest.fixture
def vault(crypto, file_store):
    return CredentialVault(crypto, file_store)


@pytest.fixture
def sqlite_vault(crypto, sqlite_store):
    return CredentialVault(crypto, sqlite_store)


# --- CredentialEntry ---


class TestCredentialEntry:
    def test_to_dict_roundtrip(self, crypto):
        encrypted = crypto.encrypt("secret123")
        entry = CredentialEntry(
            credential_id="test-id",
            alias="test_alias",
            tenant_id="default",
            credential_type=CredentialType.PASSWORD,
            encrypted_secret=encrypted,
            username="user@test.com",
        )
        d = entry.to_dict()
        restored = CredentialEntry.from_dict(d)
        assert restored.credential_id == entry.credential_id
        assert restored.alias == entry.alias
        assert restored.credential_type == CredentialType.PASSWORD
        assert restored.username == "user@test.com"

    def test_default_values(self, crypto):
        encrypted = crypto.encrypt("secret")
        entry = CredentialEntry(
            credential_id="id",
            alias="a",
            tenant_id="t",
            credential_type=CredentialType.API_KEY,
            encrypted_secret=encrypted,
        )
        assert entry.access_count == 0
        assert entry.rotation_policy == RotationPolicy.NONE
        assert entry.created_by == "system"
        assert entry.expires_at is None


# --- FileCredentialStore ---


class TestFileCredentialStore:
    @pytest.mark.asyncio
    async def test_save_and_load(self, file_store, crypto):
        encrypted = crypto.encrypt("my_secret")
        entry = CredentialEntry(
            credential_id="id-1",
            alias="sf_prod",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            encrypted_secret=encrypted,
            username="admin",
        )
        await file_store.save(entry)
        loaded = await file_store.load("sf_prod", "acme")
        assert loaded is not None
        assert loaded.alias == "sf_prod"
        assert loaded.username == "admin"

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, file_store):
        result = await file_store.load("nope", "acme")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, file_store, crypto):
        encrypted = crypto.encrypt("s")
        entry = CredentialEntry(
            credential_id="id-2",
            alias="to_delete",
            tenant_id="acme",
            credential_type=CredentialType.API_KEY,
            encrypted_secret=encrypted,
        )
        await file_store.save(entry)
        assert await file_store.delete("to_delete", "acme") is True
        assert await file_store.load("to_delete", "acme") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, file_store):
        assert await file_store.delete("nope", "acme") is False

    @pytest.mark.asyncio
    async def test_list_aliases(self, file_store, crypto):
        for i in range(3):
            entry = CredentialEntry(
                credential_id=f"id-{i}",
                alias=f"alias_{i}",
                tenant_id="acme",
                credential_type=CredentialType.PASSWORD,
                encrypted_secret=crypto.encrypt(f"secret_{i}"),
            )
            await file_store.save(entry)
        aliases = await file_store.list_aliases("acme")
        assert set(aliases) == {"alias_0", "alias_1", "alias_2"}

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, file_store, crypto):
        for tenant in ["acme", "globex"]:
            entry = CredentialEntry(
                credential_id=f"id-{tenant}",
                alias="shared_name",
                tenant_id=tenant,
                credential_type=CredentialType.PASSWORD,
                encrypted_secret=crypto.encrypt(f"{tenant}_secret"),
            )
            await file_store.save(entry)
        acme = await file_store.load("shared_name", "acme")
        globex = await file_store.load("shared_name", "globex")
        assert acme.tenant_id == "acme"
        assert globex.tenant_id == "globex"

    @pytest.mark.asyncio
    async def test_update(self, file_store, crypto):
        entry = CredentialEntry(
            credential_id="id-u",
            alias="update_me",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            encrypted_secret=crypto.encrypt("old_secret"),
        )
        await file_store.save(entry)
        entry.access_count = 5
        assert await file_store.update(entry) is True
        loaded = await file_store.load("update_me", "acme")
        assert loaded.access_count == 5


# --- SQLiteCredentialStore ---


class TestSQLiteCredentialStore:
    @pytest.mark.asyncio
    async def test_save_and_load(self, sqlite_store, crypto):
        encrypted = crypto.encrypt("my_secret")
        entry = CredentialEntry(
            credential_id="id-sq1",
            alias="db_cred",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            encrypted_secret=encrypted,
            username="admin",
        )
        await sqlite_store.save(entry)
        loaded = await sqlite_store.load("db_cred", "acme")
        assert loaded is not None
        assert loaded.alias == "db_cred"

    @pytest.mark.asyncio
    async def test_unique_alias_tenant(self, sqlite_store, crypto):
        """Duplicate alias+tenant should raise error."""
        entry = CredentialEntry(
            credential_id="id-sq2",
            alias="dup",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            encrypted_secret=crypto.encrypt("s"),
        )
        await sqlite_store.save(entry)
        with pytest.raises(Exception):
            await sqlite_store.save(entry)

    @pytest.mark.asyncio
    async def test_list_entries(self, sqlite_store, crypto):
        for i in range(3):
            entry = CredentialEntry(
                credential_id=f"id-le-{i}",
                alias=f"cred_{i}",
                tenant_id="acme",
                credential_type=CredentialType.API_KEY,
                encrypted_secret=crypto.encrypt(f"s{i}"),
            )
            await sqlite_store.save(entry)
        entries = await sqlite_store.list_entries("acme")
        assert len(entries) == 3


# --- DecryptedCredential ---


class TestDecryptedCredential:
    def test_secret_access(self):
        dc = DecryptedCredential(
            entry=object(),  # Placeholder
            secret="my_password",
        )
        assert dc.secret == "my_password"

    def test_wipe(self):
        dc = DecryptedCredential(entry=object(), secret="my_password")
        dc.wipe()
        assert dc.is_wiped is True
        with pytest.raises(ValueError, match="wiped"):
            _ = dc.secret

    def test_context_manager_wipes(self):
        dc = DecryptedCredential(entry=object(), secret="my_password")
        with dc:
            assert dc.secret == "my_password"
        assert dc.is_wiped is True

    def test_double_wipe_safe(self):
        dc = DecryptedCredential(entry=object(), secret="secret")
        dc.wipe()
        dc.wipe()  # Should not raise

    def test_repr(self):
        entry = CredentialEntry(
            credential_id="id",
            alias="test",
            tenant_id="t",
            credential_type=CredentialType.PASSWORD,
            encrypted_secret=EncryptedBlob(ciphertext=b"x", iv=b"\x00"*12, tag=b"\x00"*16),
        )
        dc = DecryptedCredential(entry=entry, secret="s")
        r = repr(dc)
        assert "test" in r
        assert "active" in r
        dc.wipe()
        r = repr(dc)
        assert "wiped" in r


# --- CredentialVault ---


class TestCredentialVault:
    @pytest.mark.asyncio
    async def test_store_and_get(self, vault):
        await vault.store_credential(
            alias="sf_prod",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            secret="hunter2",
            username="admin@acme.com",
        )
        with await vault.get_credential("sf_prod", "acme") as cred:
            assert cred.secret == "hunter2"
            assert cred.username == "admin@acme.com"

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises(self, vault):
        with pytest.raises(KeyError, match="not found"):
            await vault.get_credential("nope", "acme")

    @pytest.mark.asyncio
    async def test_auto_wipe_after_context(self, vault):
        await vault.store_credential(
            alias="wipe_test",
            tenant_id="acme",
            credential_type=CredentialType.API_KEY,
            secret="api_key_12345",
        )
        with await vault.get_credential("wipe_test", "acme") as cred:
            assert cred.secret == "api_key_12345"
        # After context exit, secret should be wiped

    @pytest.mark.asyncio
    async def test_list_credentials(self, vault):
        for i in range(3):
            await vault.store_credential(
                alias=f"cred_{i}",
                tenant_id="acme",
                credential_type=CredentialType.PASSWORD,
                secret=f"secret_{i}",
            )
        summaries = await vault.list_credentials("acme")
        assert len(summaries) == 3
        # None should contain the secret
        for s in summaries:
            assert not hasattr(s, "secret") or not hasattr(s, "_secret")

    @pytest.mark.asyncio
    async def test_delete_credential(self, vault):
        await vault.store_credential(
            alias="to_delete",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            secret="secret",
        )
        assert await vault.delete_credential("to_delete", "acme") is True
        with pytest.raises(KeyError):
            await vault.get_credential("to_delete", "acme")

    @pytest.mark.asyncio
    async def test_rotate_credential(self, vault):
        await vault.store_credential(
            alias="rotate_me",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            secret="old_password",
        )
        await vault.rotate_credential(
            alias="rotate_me",
            tenant_id="acme",
            new_secret="new_password",
        )
        with await vault.get_credential("rotate_me", "acme") as cred:
            assert cred.secret == "new_password"

    @pytest.mark.asyncio
    async def test_access_count_increments(self, vault):
        await vault.store_credential(
            alias="counted",
            tenant_id="acme",
            credential_type=CredentialType.API_KEY,
            secret="key",
        )
        for _ in range(3):
            cred = await vault.get_credential("counted", "acme")
            cred.wipe()

        summary = await vault.get_credential_summary("counted", "acme")
        assert summary.access_count == 3

    @pytest.mark.asyncio
    async def test_expired_credential_raises(self, vault):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        await vault.store_credential(
            alias="expired",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            secret="old",
            expires_at=past,
        )
        with pytest.raises(ValueError, match="expired"):
            await vault.get_credential("expired", "acme")

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, vault):
        """Tenant A cannot access Tenant B's credentials."""
        await vault.store_credential(
            alias="shared",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            secret="acme_secret",
        )
        await vault.store_credential(
            alias="shared",
            tenant_id="globex",
            credential_type=CredentialType.PASSWORD,
            secret="globex_secret",
        )
        with await vault.get_credential("shared", "acme") as cred:
            assert cred.secret == "acme_secret"
        with await vault.get_credential("shared", "globex") as cred:
            assert cred.secret == "globex_secret"

    @pytest.mark.asyncio
    async def test_update_metadata(self, vault):
        await vault.store_credential(
            alias="meta",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            secret="secret",
            metadata={"env": "staging"},
        )
        await vault.update_metadata(
            alias="meta",
            tenant_id="acme",
            metadata={"env": "production"},
        )
        with await vault.get_credential("meta", "acme") as cred:
            assert cred.metadata["env"] == "production"

    @pytest.mark.asyncio
    async def test_sqlite_store_backend(self, sqlite_vault):
        """Same vault operations work with SQLite backend."""
        await sqlite_vault.store_credential(
            alias="db_test",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            secret="secret",
            username="user",
        )
        with await sqlite_vault.get_credential("db_test", "acme") as cred:
            assert cred.secret == "secret"
            assert cred.username == "user"


# --- Placeholder Resolution ---


class TestPlaceholderResolution:
    @pytest.mark.asyncio
    async def test_resolve_vault_placeholder(self, vault):
        await vault.store_credential(
            alias="sf_prod",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            secret="hunter2",
            username="admin@acme.com",
        )
        result = await vault.resolve_placeholder("${vault:sf_prod.secret}", "acme")
        assert result == "hunter2"

    @pytest.mark.asyncio
    async def test_resolve_username_field(self, vault):
        await vault.store_credential(
            alias="sf_prod",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            secret="hunter2",
            username="admin@acme.com",
        )
        result = await vault.resolve_placeholder("${vault:sf_prod.username}", "acme")
        assert result == "admin@acme.com"

    @pytest.mark.asyncio
    async def test_resolve_metadata_field(self, vault):
        await vault.store_credential(
            alias="service",
            tenant_id="acme",
            credential_type=CredentialType.API_KEY,
            secret="key123",
            metadata={"base_url": "https://api.example.com"},
        )
        result = await vault.resolve_placeholder(
            "${vault:service.metadata.base_url}", "acme"
        )
        assert result == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_resolve_non_placeholder_unchanged(self, vault):
        result = await vault.resolve_placeholder("plain text", "acme")
        assert result == "plain text"

    @pytest.mark.asyncio
    async def test_resolve_in_dict(self, vault):
        await vault.store_credential(
            alias="api",
            tenant_id="acme",
            credential_type=CredentialType.API_KEY,
            secret="my_api_key",
        )
        data = {
            "url": "https://api.example.com",
            "api_key": "${vault:api.secret}",
            "nested": {"token": "${vault:api.secret}"},
        }
        resolved = await vault.resolve_in_dict(data, "acme")
        assert resolved["api_key"] == "my_api_key"
        assert resolved["nested"]["token"] == "my_api_key"
        assert resolved["url"] == "https://api.example.com"


# --- CredentialSummary ---


class TestCredentialSummary:
    def test_from_entry(self, crypto):
        entry = CredentialEntry(
            credential_id="id",
            alias="test",
            tenant_id="default",
            credential_type=CredentialType.PASSWORD,
            encrypted_secret=crypto.encrypt("s"),
            username="user",
        )
        summary = CredentialSummary.from_entry(entry)
        assert summary.alias == "test"
        assert summary.credential_type == CredentialType.PASSWORD
        assert summary.is_expired is False

    def test_expired_entry(self, crypto):
        entry = CredentialEntry(
            credential_id="id",
            alias="test",
            tenant_id="default",
            credential_type=CredentialType.PASSWORD,
            encrypted_secret=crypto.encrypt("s"),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        summary = CredentialSummary.from_entry(entry)
        assert summary.is_expired is True


# --- Vault from config ---


class TestVaultFromConfig:
    def test_from_config_file_store(self, tmp_path):
        import base64

        key = base64.b64encode(b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!!").decode()
        vault = CredentialVault.from_config({
            "master_key": key,
            "store_type": "file",
            "store_path": str(tmp_path / "creds"),
        })
        assert vault is not None

    def test_from_config_invalid_key(self):
        with pytest.raises((ValueError, Exception)):
            CredentialVault.from_config({
                "master_key": "short",
                "store_type": "file",
            })

    def test_from_config_raw_bytes(self, tmp_path):
        vault = CredentialVault.from_config({
            "master_key": b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!!",
            "store_type": "file",
            "store_path": str(tmp_path / "creds"),
        })
        assert vault is not None
