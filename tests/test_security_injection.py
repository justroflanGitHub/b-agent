"""Tests for credential injection integration into BrowserAgent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from browser_agent.security.credential_vault import (
    CredentialVault,
    CredentialType,
    FileCredentialStore,
)
from browser_agent.security.crypto import CryptoEngine


@pytest.fixture
def crypto():
    return CryptoEngine(master_key=b'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!!')


@pytest.fixture
def vault(crypto, tmp_path):
    store = FileCredentialStore(str(tmp_path / "creds"))
    return CredentialVault(crypto, store)


class TestAgentCredentialResolution:
    """Test credential placeholder resolution in agent context."""

    @pytest.mark.asyncio
    async def test_resolve_vault_placeholder_in_text(self, vault):
        """Agent can resolve ${vault:alias.field} in goal text."""
        await vault.store_credential(
            alias="sf_prod",
            tenant_id="default",
            credential_type=CredentialType.PASSWORD,
            secret="hunter2",
            username="admin@acme.com",
        )

        # Simulate what the agent does
        text = "Log into Salesforce with ${vault:sf_prod.username}"
        import re

        vault_pattern = r'\$\{vault:([^.}]+)\.?([^}]*)\}'
        for match in re.finditer(vault_pattern, text):
            alias = match.group(1)
            field = match.group(2) or "secret"
            cred = await vault.get_credential(alias, "default")
            try:
                if field == "username":
                    value = cred.username or ""
                else:
                    value = cred.secret
                text = text.replace(match.group(0), value)
            finally:
                cred.wipe()

        assert text == "Log into Salesforce with admin@acme.com"

    @pytest.mark.asyncio
    async def test_resolve_multiple_placeholders(self, vault):
        """Multiple placeholders in one string."""
        await vault.store_credential(
            alias="portal",
            tenant_id="default",
            credential_type=CredentialType.PASSWORD,
            secret="pass123",
            username="user@test.com",
        )

        text = "Login as ${vault:portal.username} with ${vault:portal.secret}"
        resolved = await vault.resolve_placeholder("${vault:portal.username}", "default")
        text = text.replace("${vault:portal.username}", resolved)

        resolved = await vault.resolve_placeholder("${vault:portal.secret}", "default")
        text = text.replace("${vault:portal.secret}", resolved)

        assert text == "Login as user@test.com with pass123"

    @pytest.mark.asyncio
    async def test_credential_aliases_dict(self, vault):
        """Test simple field mapping via credential_aliases."""
        await vault.store_credential(
            alias="api_service",
            tenant_id="default",
            credential_type=CredentialType.API_KEY,
            secret="sk-abc123",
        )

        # Simulate resolve_in_dict with alias mapping
        data = {"api_key": "${vault:api_service.secret}"}
        resolved = await vault.resolve_in_dict(data, "default")
        assert resolved["api_key"] == "sk-abc123"


class TestAgentInitWithVault:
    """Test BrowserAgent initialization with credential vault."""

    def test_agent_accepts_vault(self):
        from browser_agent.agent import BrowserAgent

        crypto = CryptoEngine(master_key=b'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!!')
        store = MagicMock()
        vault = CredentialVault(crypto, store)

        agent = BrowserAgent(credential_vault=vault, tenant_id="acme")
        assert agent.credential_vault is vault
        assert agent.tenant_id == "acme"

    def test_agent_without_vault(self):
        from browser_agent.agent import BrowserAgent

        agent = BrowserAgent()
        assert agent.credential_vault is None
        assert agent.tenant_id == "default"

    def test_stats_include_vault_status(self):
        from browser_agent.agent import BrowserAgent

        agent = BrowserAgent()
        stats = agent.get_stats()
        assert "credential_vault_enabled" in stats
        assert stats["credential_vault_enabled"] is False
        assert stats["tenant_id"] == "default"
