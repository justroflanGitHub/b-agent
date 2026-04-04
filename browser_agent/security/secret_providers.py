"""External secret provider integrations.

Supports:
- Environment variables (dev/local)
- HashiCorp Vault (production)
- AWS Secrets Manager (AWS deployments)
- Azure Key Vault (Azure deployments)
- ChainedProvider (fallback chain)
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SecretProvider(ABC):
    """Interface for external secret management systems."""

    @abstractmethod
    async def get_secret(self, path: str) -> Dict[str, str]:
        """Fetch secret from external provider.

        Args:
            path: Secret path/key (provider-specific format).

        Returns:
            Dict of key-value pairs (e.g., {"username": "...", "password": "..."}).

        Raises:
            SecretNotFoundError: Secret doesn't exist.
            ProviderError: Connection or auth error.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Check connectivity to provider."""

    async def get_secret_field(self, path: str, field: str) -> str:
        """Fetch a specific field from a secret."""
        secret = await self.get_secret(path)
        if field not in secret:
            raise KeyError(f"Field '{field}' not found in secret at '{path}'")
        return secret[field]


class SecretNotFoundError(Exception):
    """Raised when a secret is not found in the provider."""



class ProviderError(Exception):
    """Raised when the provider connection or auth fails."""



class EnvironmentProvider(SecretProvider):
    """Load secrets from environment variables (dev/local mode).

    Pattern:
        CREDENTIAL_{ALIAS}_SECRET     → secret value
        CREDENTIAL_{ALIAS}_USERNAME   → username
        CREDENTIAL_{ALIAS}_FIELD_{X}  → additional fields

    Example:
        CREDENTIAL_SF_PROD_SECRET=admin_pass
        CREDENTIAL_SF_PROD_USERNAME=admin@corp.com
    """

    def __init__(self, prefix: str = "CREDENTIAL_"):
        self._prefix = prefix

    def _env_key(self, alias: str, field: str) -> str:
        safe_alias = alias.upper().replace("-", "_").replace(".", "_")
        safe_field = field.upper()
        return f"{self._prefix}{safe_alias}_{safe_field}"

    async def get_secret(self, path: str) -> Dict[str, str]:
        result: Dict[str, str] = {}

        # Look for SECRET field
        secret_key = self._env_key(path, "SECRET")
        if secret_key in os.environ:
            result["secret"] = os.environ[secret_key]

        # Look for USERNAME field
        username_key = self._env_key(path, "USERNAME")
        if username_key in os.environ:
            result["username"] = os.environ[username_key]

        # Look for any additional FIELD_* fields
        prefix = f"{self._prefix}{path.upper().replace('-', '_').replace('.', '_')}_"
        for key, value in os.environ.items():
            if key.startswith(prefix) and key not in (secret_key, username_key):
                # Strip prefix to get field name
                field_name = key[len(prefix) :].lower()
                result[field_name] = value

        if not result:
            raise SecretNotFoundError(
                f"No environment variables found for credential '{path}' " f"(looked for {secret_key})"
            )

        return result

    async def health_check(self) -> bool:
        return True  # Environment is always available


class HashiCorpVaultProvider(SecretProvider):
    """HashiCorp Vault integration via hvac library.

    Supports KV v2 secret engine with AppRole, Kubernetes, and token auth.

    Required config:
        url: Vault server URL
        auth_method: "approle", "kubernetes", or "token"
        role_id + secret_id (for approle)
        jwt_path (for kubernetes)
        token (for token auth)
    """

    def __init__(
        self,
        url: str,
        auth_method: str = "token",
        token: Optional[str] = None,
        role_id: Optional[str] = None,
        secret_id: Optional[str] = None,
        jwt_path: Optional[str] = None,
        mount_point: str = "secret",
        namespace: Optional[str] = None,
    ):
        self._url = url
        self._auth_method = auth_method
        self._token = token
        self._role_id = role_id
        self._secret_id = secret_id
        self._jwt_path = jwt_path
        self._mount_point = mount_point
        self._namespace = namespace
        self._client = None

    def _get_client(self):
        try:
            import hvac
        except ImportError:
            raise ProviderError("hvac package not installed. Install with: pip install hvac")

        client = hvac.Client(url=self._url, namespace=self._namespace)

        if self._auth_method == "token":
            if not self._token:
                raise ProviderError("Token auth requires 'token' config")
            client.token = self._token
        elif self._auth_method == "approle":
            if not self._role_id or not self._secret_id:
                raise ProviderError("AppRole auth requires 'role_id' and 'secret_id'")
            auth = client.auth.approle.login(
                role_id=self._role_id,
                secret_id=self._secret_id,
            )
            client.token = auth["auth"]["client_token"]
        elif self._auth_method == "kubernetes":
            if not self._jwt_path:
                self._jwt_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
            with open(self._jwt_path, "r") as f:
                jwt = f.read().strip()
            auth = client.auth.kubernetes.login(
                role=self._role_id or "default",
                jwt=jwt,
            )
            client.token = auth["auth"]["client_token"]
        else:
            raise ProviderError(f"Unsupported auth method: {self._auth_method}")

        if not client.is_authenticated():
            raise ProviderError("Vault authentication failed")

        self._client = client
        return client

    async def get_secret(self, path: str) -> Dict[str, str]:
        try:
            client = self._client or self._get_client()
            # KV v2: path is relative to mount point
            response = client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self._mount_point,
            )
            return response["data"]["data"]
        except Exception as e:
            if "InvalidPath" in str(e) or "no data" in str(e).lower():
                raise SecretNotFoundError(f"Secret not found at path: {path}")
            raise ProviderError(f"Vault error: {e}") from e

    async def health_check(self) -> bool:
        try:
            client = self._client or self._get_client()
            return client.is_authenticated()
        except Exception:
            return False


class AWSSecretsManagerProvider(SecretProvider):
    """AWS Secrets Manager integration via boto3.

    Required config:
        region_name: AWS region
        access_key_id (optional, uses IAM role if not set)
        secret_access_key (optional)
    """

    def __init__(
        self,
        region_name: str = "us-east-1",
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ):
        self._region = region_name
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._client = None

    def _get_client(self):
        try:
            import boto3
        except ImportError:
            raise ProviderError("boto3 package not installed. Install with: pip install boto3")

        kwargs = {"region_name": self._region}
        if self._access_key_id and self._secret_access_key:
            kwargs["aws_access_key_id"] = self._access_key_id
            kwargs["aws_secret_access_key"] = self._secret_access_key

        self._client = boto3.client("secretsmanager", **kwargs)
        return self._client

    async def get_secret(self, path: str) -> Dict[str, str]:
        try:
            client = self._client or self._get_client()
            response = client.get_secret_value(SecretId=path)

            if "SecretString" in response:
                secret_string = response["SecretString"]
                try:
                    return json.loads(secret_string)
                except json.JSONDecodeError:
                    return {"secret": secret_string}
            else:
                return {"secret": response["SecretBinary"].decode("utf-8")}

        except Exception as e:
            error_name = type(e).__name__
            if "ResourceNotFound" in error_name or "ResourceNotFound" in str(e):
                raise SecretNotFoundError(f"Secret not found: {path}")
            raise ProviderError(f"AWS Secrets Manager error: {e}") from e

    async def health_check(self) -> bool:
        try:
            client = self._client or self._get_client()
            client.list_secrets(MaxResults=1)
            return True
        except Exception:
            return False


class AzureKeyVaultProvider(SecretProvider):
    """Azure Key Vault integration.

    Required config:
        vault_url: Key Vault URL (e.g., https://myvault.vault.azure.net/)
        tenant_id, client_id, client_secret (for service principal auth)
        or use managed identity (default)
    """

    def __init__(
        self,
        vault_url: str,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self._vault_url = vault_url
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._client = None

    def _get_client(self):
        try:
            from azure.identity import DefaultAzureCredential, ClientSecretCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError:
            raise ProviderError(
                "Azure packages not installed. Install with: " "pip install azure-identity azure-keyvault-secrets"
            )

        if self._tenant_id and self._client_id and self._client_secret:
            credential = ClientSecretCredential(
                tenant_id=self._tenant_id,
                client_id=self._client_id,
                client_secret=self._client_secret,
            )
        else:
            credential = DefaultAzureCredential()

        self._client = SecretClient(vault_url=self._vault_url, credential=credential)
        return self._client

    async def get_secret(self, path: str) -> Dict[str, str]:
        try:
            client = self._client or self._get_client()
            # Azure Key Vault uses secret names (no paths)
            # Support path format: "secret-name" or "secret-name/version"
            parts = path.split("/")
            secret_name = parts[0]
            version = parts[1] if len(parts) > 1 else None

            secret = client.get_secret(secret_name, version=version)
            result = {"secret": secret.value}

            # Try to parse as JSON for structured secrets
            try:
                parsed = json.loads(secret.value)
                if isinstance(parsed, dict):
                    result.update(parsed)
            except (json.JSONDecodeError, TypeError):
                pass

            return result

        except Exception as e:
            if "SecretNotFound" in str(e):
                raise SecretNotFoundError(f"Secret not found: {path}")
            raise ProviderError(f"Azure Key Vault error: {e}") from e

    async def health_check(self) -> bool:
        try:
            client = self._client or self._get_client()
            # List one secret to verify connectivity
            list(client.list_properties_of_secrets())
            return True
        except Exception:
            return False


class ChainedProvider(SecretProvider):
    """Try multiple providers in order with fallback.

    First successful response wins. If all fail, raises the last error.

    Example:
        provider = ChainedProvider([
            HashiCorpVaultProvider(...),
            EnvironmentProvider(),
        ])
        # Tries Vault first, falls back to env vars
    """

    def __init__(self, providers: List[SecretProvider]):
        if not providers:
            raise ValueError("ChainedProvider requires at least one provider")
        self._providers = providers

    async def get_secret(self, path: str) -> Dict[str, str]:
        last_error = None
        for provider in self._providers:
            try:
                return await provider.get_secret(path)
            except SecretNotFoundError as e:
                last_error = e
                logger.debug(
                    "Provider %s: secret not found at %s, trying next",
                    type(provider).__name__,
                    path,
                )
                continue
            except ProviderError as e:
                last_error = e
                logger.warning(
                    "Provider %s: error fetching %s: %s, trying next",
                    type(provider).__name__,
                    path,
                    e,
                )
                continue

        if last_error:
            raise last_error
        raise SecretNotFoundError(f"Secret not found at '{path}' (all providers exhausted)")

    async def health_check(self) -> bool:
        """At least one provider must be healthy."""
        for provider in self._providers:
            if await provider.health_check():
                return True
        return False

    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all providers individually."""
        results = {}
        for provider in self._providers:
            name = type(provider).__name__
            try:
                results[name] = await provider.health_check()
            except Exception:
                results[name] = False
        return results
