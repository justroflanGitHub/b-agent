"""Tests for browser_agent.security.secret_providers — External secret providers."""

import os
import pytest

from browser_agent.security.secret_providers import (
    ChainedProvider,
    EnvironmentProvider,
    ProviderError,
    SecretNotFoundError,
)


class TestEnvironmentProvider:
    @pytest.fixture
    def provider(self):
        return EnvironmentProvider()

    @pytest.mark.asyncio
    async def test_get_secret(self, provider, monkeypatch):
        monkeypatch.setenv("CREDENTIAL_SF_PROD_SECRET", "hunter2")
        monkeypatch.setenv("CREDENTIAL_SF_PROD_USERNAME", "admin@acme.com")

        result = await provider.get_secret("sf_prod")
        assert result["secret"] == "hunter2"
        assert result["username"] == "admin@acme.com"

    @pytest.mark.asyncio
    async def test_get_secret_not_found(self, provider):
        with pytest.raises(SecretNotFoundError):
            await provider.get_secret("nonexistent_credential_xyz")

    @pytest.mark.asyncio
    async def test_get_secret_field(self, provider, monkeypatch):
        monkeypatch.setenv("CREDENTIAL_MY_API_SECRET", "key123")
        result = await provider.get_secret_field("my_api", "secret")
        assert result == "key123"

    @pytest.mark.asyncio
    async def test_get_secret_field_missing(self, provider, monkeypatch):
        monkeypatch.setenv("CREDENTIAL_MY_API_SECRET", "key123")
        with pytest.raises(KeyError, match="nonexistent_field"):
            await provider.get_secret_field("my_api", "nonexistent_field")

    @pytest.mark.asyncio
    async def test_health_check(self, provider):
        assert await provider.health_check() is True

    @pytest.mark.asyncio
    async def test_custom_prefix(self, monkeypatch):
        provider = EnvironmentProvider(prefix="MYAPP_")
        monkeypatch.setenv("MYAPP_DB_SECRET", "db_pass")
        result = await provider.get_secret("db")
        assert result["secret"] == "db_pass"

    @pytest.mark.asyncio
    async def test_additional_fields(self, provider, monkeypatch):
        monkeypatch.setenv("CREDENTIAL_SVC_SECRET", "pass")
        monkeypatch.setenv("CREDENTIAL_SVC_USERNAME", "user")
        monkeypatch.setenv("CREDENTIAL_SVC_REGION", "us-east-1")

        result = await provider.get_secret("svc")
        assert result["secret"] == "pass"
        assert result["username"] == "user"
        assert result["region"] == "us-east-1"


class TestChainedProvider:
    @pytest.mark.asyncio
    async def test_first_provider_succeeds(self, monkeypatch):
        p1 = EnvironmentProvider(prefix="PRIMARY_")
        p2 = EnvironmentProvider(prefix="FALLBACK_")

        monkeypatch.setenv("PRIMARY_DB_SECRET", "primary_pass")

        chain = ChainedProvider([p1, p2])
        result = await chain.get_secret("db")
        assert result["secret"] == "primary_pass"

    @pytest.mark.asyncio
    async def test_fallback_to_second(self, monkeypatch):
        p1 = EnvironmentProvider(prefix="MISSING_")
        p2 = EnvironmentProvider(prefix="FALLBACK_")

        monkeypatch.setenv("FALLBACK_DB_SECRET", "fallback_pass")

        chain = ChainedProvider([p1, p2])
        result = await chain.get_secret("db")
        assert result["secret"] == "fallback_pass"

    @pytest.mark.asyncio
    async def test_all_providers_fail(self):
        p1 = EnvironmentProvider(prefix="NOPE1_")
        p2 = EnvironmentProvider(prefix="NOPE2_")

        chain = ChainedProvider([p1, p2])
        with pytest.raises(SecretNotFoundError):
            await chain.get_secret("totally_missing")

    @pytest.mark.asyncio
    async def test_health_check_any_healthy(self):
        p1 = EnvironmentProvider()
        chain = ChainedProvider([p1])
        assert await chain.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_all(self):
        p1 = EnvironmentProvider()
        p2 = EnvironmentProvider()
        chain = ChainedProvider([p1, p2])
        results = await chain.health_check_all()
        assert results["EnvironmentProvider"] is True

    def test_empty_providers_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            ChainedProvider([])
