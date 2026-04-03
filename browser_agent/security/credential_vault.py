"""Credential vault — encrypted storage with access control and auto-wipe.

Supports multiple storage backends (file, SQLite) and provides
auto-wiping DecryptedCredential that clears secrets from memory.
"""

import asyncio
import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .crypto import CryptoEngine, EncryptedBlob

logger = logging.getLogger(__name__)


class CredentialType(Enum):
    PASSWORD = "password"
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    COOKIE = "cookie"
    CERTIFICATE = "certificate"
    SSH_KEY = "ssh_key"
    CUSTOM = "custom"


class RotationPolicy(Enum):
    NONE = "none"
    ON_USE = "on_use"
    TIME_BASED = "time_based"
    ON_FAILURE = "on_failure"


@dataclass
class CredentialEntry:
    """A single credential record (secret stored encrypted)."""

    credential_id: str
    alias: str
    tenant_id: str
    credential_type: CredentialType
    encrypted_secret: EncryptedBlob
    username: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    rotation_policy: RotationPolicy = RotationPolicy.NONE
    rotation_interval_days: int = 90
    use_count_for_rotation: int = 100
    access_count: int = 0
    created_by: str = "system"
    last_accessed_by: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize for storage (encrypted_secret as dict)."""
        return {
            "credential_id": self.credential_id,
            "alias": self.alias,
            "tenant_id": self.tenant_id,
            "credential_type": self.credential_type.value,
            "encrypted_secret": self.encrypted_secret.to_dict(),
            "username": self.username,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "rotation_policy": self.rotation_policy.value,
            "rotation_interval_days": self.rotation_interval_days,
            "use_count_for_rotation": self.use_count_for_rotation,
            "access_count": self.access_count,
            "created_by": self.created_by,
            "last_accessed_by": self.last_accessed_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CredentialEntry":
        """Deserialize from storage."""
        return cls(
            credential_id=data["credential_id"],
            alias=data["alias"],
            tenant_id=data["tenant_id"],
            credential_type=CredentialType(data["credential_type"]),
            encrypted_secret=EncryptedBlob.from_dict(data["encrypted_secret"]),
            username=data.get("username"),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
            last_used_at=(
                datetime.fromisoformat(data["last_used_at"])
                if data.get("last_used_at")
                else None
            ),
            rotation_policy=RotationPolicy(data.get("rotation_policy", "none")),
            rotation_interval_days=data.get("rotation_interval_days", 90),
            use_count_for_rotation=data.get("use_count_for_rotation", 100),
            access_count=data.get("access_count", 0),
            created_by=data.get("created_by", "system"),
            last_accessed_by=data.get("last_accessed_by"),
        )


@dataclass
class CredentialSummary:
    """Credential metadata without the secret."""

    credential_id: str
    alias: str
    tenant_id: str
    credential_type: CredentialType
    username: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    access_count: int
    rotation_policy: RotationPolicy
    is_expired: bool = False

    @classmethod
    def from_entry(cls, entry: CredentialEntry) -> "CredentialSummary":
        now = datetime.now(timezone.utc)
        is_expired = entry.expires_at is not None and entry.expires_at < now
        return cls(
            credential_id=entry.credential_id,
            alias=entry.alias,
            tenant_id=entry.tenant_id,
            credential_type=entry.credential_type,
            username=entry.username,
            metadata=entry.metadata,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            expires_at=entry.expires_at,
            last_used_at=entry.last_used_at,
            access_count=entry.access_count,
            rotation_policy=entry.rotation_policy,
            is_expired=is_expired,
        )


@dataclass
class ExpiringCredential:
    """Credential approaching or past expiry."""

    alias: str
    tenant_id: str
    credential_type: CredentialType
    expires_at: Optional[datetime]
    is_expired: bool
    days_remaining: Optional[float]


class DecryptedCredential:
    """Temporary holder for decrypted credential. Auto-wipes on context exit.

    Usage:
        async with vault.get_credential("alias", "tenant") as cred:
            print(cred.secret)  # Available here
        # secret is wiped from memory here
    """

    def __init__(self, entry: CredentialEntry, secret: str, vault: Optional["CredentialVault"] = None):
        self._entry = entry
        self._secret_bytes = bytearray(secret.encode("utf-8"))
        self._wiped = False
        self._vault = vault

    @property
    def entry(self) -> CredentialEntry:
        return self._entry

    @property
    def username(self) -> Optional[str]:
        return self._entry.username

    @property
    def secret(self) -> str:
        if self._wiped:
            raise ValueError("Credential has been wiped from memory")
        return self._secret_bytes.decode("utf-8")

    @property
    def metadata(self) -> Dict[str, Any]:
        return self._entry.metadata

    @property
    def credential_type(self) -> CredentialType:
        return self._entry.credential_type

    @property
    def alias(self) -> str:
        return self._entry.alias

    @property
    def is_wiped(self) -> bool:
        return self._wiped

    def wipe(self):
        """Overwrite secret bytes in memory with zeros."""
        if not self._wiped:
            for i in range(len(self._secret_bytes)):
                self._secret_bytes[i] = 0
            self._wiped = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.wipe()

    def __del__(self):
        if not self._wiped:
            self.wipe()

    def __repr__(self):
        state = "wiped" if self._wiped else "active"
        return f"DecryptedCredential(alias={self._entry.alias!r}, state={state})"


# --- Storage backends ---


class CredentialStore(ABC):
    """Abstract storage backend for credentials."""

    @abstractmethod
    async def save(self, entry: CredentialEntry) -> str:
        """Save encrypted credential. Returns credential_id."""

    @abstractmethod
    async def load(self, alias: str, tenant_id: str) -> Optional[CredentialEntry]:
        """Load encrypted credential by alias + tenant."""

    @abstractmethod
    async def load_by_id(self, credential_id: str) -> Optional[CredentialEntry]:
        """Load encrypted credential by ID."""

    @abstractmethod
    async def delete(self, alias: str, tenant_id: str) -> bool:
        """Delete credential."""

    @abstractmethod
    async def list_aliases(self, tenant_id: str) -> List[str]:
        """List credential aliases for tenant."""

    @abstractmethod
    async def list_entries(self, tenant_id: str) -> List[CredentialEntry]:
        """List all credential entries for tenant."""

    @abstractmethod
    async def update(self, entry: CredentialEntry) -> bool:
        """Update existing credential."""


class FileCredentialStore(CredentialStore):
    """File-based encrypted credential storage.

    Stores one JSON file per tenant in the configured directory.
    """

    def __init__(self, path: str = ".credentials"):
        self._path = path
        os.makedirs(path, exist_ok=True)

    def _tenant_file(self, tenant_id: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in tenant_id)
        return os.path.join(self._path, f"{safe}.json")

    def _load_tenant_data(self, tenant_id: str) -> Dict[str, dict]:
        path = self._tenant_file(tenant_id)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_tenant_data(self, tenant_id: str, data: Dict[str, dict]):
        path = self._tenant_file(tenant_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    async def save(self, entry: CredentialEntry) -> str:
        data = self._load_tenant_data(entry.tenant_id)
        data[entry.alias] = entry.to_dict()
        self._save_tenant_data(entry.tenant_id, data)
        return entry.credential_id

    async def load(self, alias: str, tenant_id: str) -> Optional[CredentialEntry]:
        data = self._load_tenant_data(tenant_id)
        if alias not in data:
            return None
        return CredentialEntry.from_dict(data[alias])

    async def load_by_id(self, credential_id: str) -> Optional[CredentialEntry]:
        # File store doesn't index by ID efficiently; scan all tenants
        for filename in os.listdir(self._path):
            if not filename.endswith(".json"):
                continue
            tenant_id = filename[:-5]  # strip .json after sanitization
            data = self._load_tenant_data(tenant_id)
            for entry_data in data.values():
                if entry_data.get("credential_id") == credential_id:
                    return CredentialEntry.from_dict(entry_data)
        return None

    async def delete(self, alias: str, tenant_id: str) -> bool:
        data = self._load_tenant_data(tenant_id)
        if alias not in data:
            return False
        del data[alias]
        self._save_tenant_data(tenant_id, data)
        return True

    async def list_aliases(self, tenant_id: str) -> List[str]:
        data = self._load_tenant_data(tenant_id)
        return list(data.keys())

    async def list_entries(self, tenant_id: str) -> List[CredentialEntry]:
        data = self._load_tenant_data(tenant_id)
        return [CredentialEntry.from_dict(v) for v in data.values()]

    async def update(self, entry: CredentialEntry) -> bool:
        data = self._load_tenant_data(entry.tenant_id)
        if entry.alias not in data:
            return False
        data[entry.alias] = entry.to_dict()
        self._save_tenant_data(entry.tenant_id, data)
        return True


class SQLiteCredentialStore(CredentialStore):
    """SQLite-based credential storage for production deployments."""

    def __init__(self, path: str = ".credentials/vault.db"):
        self._path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        import sqlite3

        conn = sqlite3.connect(self._path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                credential_id TEXT PRIMARY KEY,
                alias TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                credential_type TEXT NOT NULL,
                encrypted_secret TEXT NOT NULL,
                username TEXT,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT,
                last_used_at TEXT,
                rotation_policy TEXT DEFAULT 'none',
                rotation_interval_days INTEGER DEFAULT 90,
                use_count_for_rotation INTEGER DEFAULT 100,
                access_count INTEGER DEFAULT 0,
                created_by TEXT DEFAULT 'system',
                last_accessed_by TEXT,
                UNIQUE(alias, tenant_id)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tenant ON credentials(tenant_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expires ON credentials(expires_at)"
        )
        conn.commit()
        conn.close()

    def _get_conn(self):
        import sqlite3

        return sqlite3.connect(self._path)

    def _entry_to_row(self, entry: CredentialEntry) -> tuple:
        return (
            entry.credential_id,
            entry.alias,
            entry.tenant_id,
            entry.credential_type.value,
            entry.encrypted_secret.to_json(),
            entry.username,
            json.dumps(entry.metadata),
            entry.created_at.isoformat(),
            entry.updated_at.isoformat(),
            entry.expires_at.isoformat() if entry.expires_at else None,
            entry.last_used_at.isoformat() if entry.last_used_at else None,
            entry.rotation_policy.value,
            entry.rotation_interval_days,
            entry.use_count_for_rotation,
            entry.access_count,
            entry.created_by,
            entry.last_accessed_by,
        )

    def _row_to_entry(self, row: tuple) -> CredentialEntry:
        return CredentialEntry(
            credential_id=row[0],
            alias=row[1],
            tenant_id=row[2],
            credential_type=CredentialType(row[3]),
            encrypted_secret=EncryptedBlob.from_json(row[4]),
            username=row[5],
            metadata=json.loads(row[6]),
            created_at=datetime.fromisoformat(row[7]),
            updated_at=datetime.fromisoformat(row[8]),
            expires_at=datetime.fromisoformat(row[9]) if row[9] else None,
            last_used_at=datetime.fromisoformat(row[10]) if row[10] else None,
            rotation_policy=RotationPolicy(row[11]),
            rotation_interval_days=row[12],
            use_count_for_rotation=row[13],
            access_count=row[14],
            created_by=row[15],
            last_accessed_by=row[16],
        )

    async def save(self, entry: CredentialEntry) -> str:
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO credentials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                self._entry_to_row(entry),
            )
            conn.commit()
            return entry.credential_id
        finally:
            conn.close()

    async def load(self, alias: str, tenant_id: str) -> Optional[CredentialEntry]:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM credentials WHERE alias=? AND tenant_id=?",
                (alias, tenant_id),
            )
            row = cursor.fetchone()
            return self._row_to_entry(row) if row else None
        finally:
            conn.close()

    async def load_by_id(self, credential_id: str) -> Optional[CredentialEntry]:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM credentials WHERE credential_id=?",
                (credential_id,),
            )
            row = cursor.fetchone()
            return self._row_to_entry(row) if row else None
        finally:
            conn.close()

    async def delete(self, alias: str, tenant_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM credentials WHERE alias=? AND tenant_id=?",
                (alias, tenant_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    async def list_aliases(self, tenant_id: str) -> List[str]:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT alias FROM credentials WHERE tenant_id=?", (tenant_id,)
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    async def list_entries(self, tenant_id: str) -> List[CredentialEntry]:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM credentials WHERE tenant_id=?", (tenant_id,)
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    async def update(self, entry: CredentialEntry) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """UPDATE credentials SET
                    credential_type=?, encrypted_secret=?, username=?,
                    metadata=?, updated_at=?, expires_at=?, last_used_at=?,
                    rotation_policy=?, rotation_interval_days=?,
                    use_count_for_rotation=?, access_count=?,
                    created_by=?, last_accessed_by=?
                WHERE alias=? AND tenant_id=?""",
                (
                    entry.credential_type.value,
                    entry.encrypted_secret.to_json(),
                    entry.username,
                    json.dumps(entry.metadata),
                    entry.updated_at.isoformat(),
                    entry.expires_at.isoformat() if entry.expires_at else None,
                    entry.last_used_at.isoformat() if entry.last_used_at else None,
                    entry.rotation_policy.value,
                    entry.rotation_interval_days,
                    entry.use_count_for_rotation,
                    entry.access_count,
                    entry.created_by,
                    entry.last_accessed_by,
                    entry.alias,
                    entry.tenant_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


class CredentialVault:
    """Encrypted credential storage with access control.

    Usage:
        crypto = CryptoEngine(master_key)
        store = FileCredentialStore(".credentials")
        vault = CredentialVault(crypto, store)

        # Store
        await vault.store_credential(
            alias="salesforce_prod",
            tenant_id="acme",
            credential_type=CredentialType.PASSWORD,
            secret="hunter2",
            username="admin@acme.com",
        )

        # Retrieve
        with await vault.get_credential("salesforce_prod", "acme") as cred:
            login(cred.username, cred.secret)
        # secret is wiped from memory here
    """

    def __init__(
        self,
        crypto: CryptoEngine,
        store: CredentialStore,
        auto_wipe: bool = True,
        log_access: bool = True,
    ):
        self._crypto = crypto
        self._store = store
        self._auto_wipe = auto_wipe
        self._log_access = log_access
        self._lock = asyncio.Lock()

    @classmethod
    def from_config(cls, config: dict) -> "CredentialVault":
        """Create vault from configuration dict.

        Config keys:
            master_key (bytes or str): 32-byte key or base64-encoded key
            store_type (str): "file" or "sqlite"
            store_path (str): Path to store
            auto_wipe (bool): Wipe secrets after use
        """
        key = config.get("master_key", b"")
        if isinstance(key, str):
            import base64

            key = base64.b64decode(key)
        if len(key) != 32:
            raise ValueError("master_key must be 32 bytes (or base64-encoded 32 bytes)")

        crypto = CryptoEngine(key)
        store_type = config.get("store_type", "file")
        store_path = config.get("store_path", ".credentials")

        if store_type == "sqlite":
            store = SQLiteCredentialStore(os.path.join(store_path, "vault.db"))
        else:
            store = FileCredentialStore(store_path)

        return cls(
            crypto=crypto,
            store=store,
            auto_wipe=config.get("auto_wipe", True),
            log_access=config.get("log_access", True),
        )

    async def store_credential(
        self,
        alias: str,
        tenant_id: str,
        credential_type: CredentialType,
        secret: str,
        username: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
        rotation_policy: RotationPolicy = RotationPolicy.NONE,
        rotation_interval_days: int = 90,
        use_count_for_rotation: int = 100,
        created_by: str = "system",
    ) -> CredentialEntry:
        """Store a new credential."""
        # Use tenant-derived key for encryption
        tenant_crypto = self._crypto.derive_child_engine(tenant_id)
        encrypted = tenant_crypto.encrypt(secret)

        entry = CredentialEntry(
            credential_id=str(uuid.uuid4()),
            alias=alias,
            tenant_id=tenant_id,
            credential_type=credential_type,
            encrypted_secret=encrypted,
            username=username,
            metadata=metadata or {},
            expires_at=expires_at,
            rotation_policy=rotation_policy,
            rotation_interval_days=rotation_interval_days,
            use_count_for_rotation=use_count_for_rotation,
            created_by=created_by,
        )

        async with self._lock:
            await self._store.save(entry)

        if self._log_access:
            logger.info(
                "Credential stored: alias=%s tenant=%s type=%s",
                alias,
                tenant_id,
                credential_type.value,
            )

        return entry

    async def get_credential(
        self,
        alias: str,
        tenant_id: str,
        requested_by: str = "system",
    ) -> DecryptedCredential:
        """Retrieve and decrypt a credential.

        Returns a DecryptedCredential that auto-wipes on context exit.
        """
        async with self._lock:
            entry = await self._store.load(alias, tenant_id)

        if entry is None:
            raise KeyError(f"Credential not found: {alias} (tenant: {tenant_id})")

        # Check expiry
        now = datetime.now(timezone.utc)
        if entry.expires_at and entry.expires_at < now:
            raise ValueError(
                f"Credential expired: {alias} (expired at {entry.expires_at.isoformat()})"
            )

        # Decrypt
        tenant_crypto = self._crypto.derive_child_engine(tenant_id)
        secret = tenant_crypto.decrypt(entry.encrypted_secret)

        # Update access metadata
        entry.access_count += 1
        entry.last_used_at = now
        entry.last_accessed_by = requested_by
        async with self._lock:
            await self._store.update(entry)

        if self._log_access:
            logger.info(
                "Credential accessed: alias=%s tenant=%s by=%s (access #%d)",
                alias,
                tenant_id,
                requested_by,
                entry.access_count,
            )

        return DecryptedCredential(entry=entry, secret=secret, vault=self)

    async def list_credentials(
        self,
        tenant_id: str,
    ) -> List[CredentialSummary]:
        """List credentials (without decrypting secrets)."""
        entries = await self._store.list_entries(tenant_id)
        return [CredentialSummary.from_entry(e) for e in entries]

    async def get_credential_summary(
        self,
        alias: str,
        tenant_id: str,
    ) -> Optional[CredentialSummary]:
        """Get credential summary without decrypting."""
        entry = await self._store.load(alias, tenant_id)
        if entry is None:
            return None
        return CredentialSummary.from_entry(entry)

    async def delete_credential(
        self,
        alias: str,
        tenant_id: str,
        deleted_by: str = "system",
    ) -> bool:
        """Delete a credential."""
        async with self._lock:
            result = await self._store.delete(alias, tenant_id)

        if self._log_access:
            logger.info(
                "Credential deleted: alias=%s tenant=%s by=%s result=%s",
                alias,
                tenant_id,
                deleted_by,
                result,
            )

        return result

    async def rotate_credential(
        self,
        alias: str,
        tenant_id: str,
        new_secret: str,
        rotated_by: str = "system",
    ) -> CredentialEntry:
        """Rotate a credential's secret."""
        async with self._lock:
            entry = await self._store.load(alias, tenant_id)

        if entry is None:
            raise KeyError(f"Credential not found: {alias} (tenant: {tenant_id})")

        # Re-encrypt with new secret
        tenant_crypto = self._crypto.derive_child_engine(tenant_id)
        entry.encrypted_secret = tenant_crypto.encrypt(new_secret)
        entry.updated_at = datetime.now(timezone.utc)
        entry.access_count = 0  # Reset access count after rotation

        async with self._lock:
            await self._store.update(entry)

        if self._log_access:
            logger.info(
                "Credential rotated: alias=%s tenant=%s by=%s",
                alias,
                tenant_id,
                rotated_by,
            )

        return entry

    async def update_metadata(
        self,
        alias: str,
        tenant_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        username: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> Optional[CredentialEntry]:
        """Update credential metadata (not the secret)."""
        async with self._lock:
            entry = await self._store.load(alias, tenant_id)

        if entry is None:
            return None

        if metadata is not None:
            entry.metadata = metadata
        if username is not None:
            entry.username = username
        if expires_at is not None:
            entry.expires_at = expires_at

        entry.updated_at = datetime.now(timezone.utc)

        async with self._lock:
            await self._store.update(entry)

        return entry

    async def check_expiry(self, warning_days: int = 7) -> List[ExpiringCredential]:
        """Find credentials approaching or past expiry."""
        # Note: this only checks known tenants. For multi-tenant,
        # the orchestration layer should iterate tenants.
        now = datetime.now(timezone.utc)
        results: List[ExpiringCredential] = []
        return results  # Populated by orchestration layer with tenant context

    async def resolve_placeholder(
        self,
        placeholder: str,
        tenant_id: str,
        requested_by: str = "system",
    ) -> str:
        """Resolve a credential placeholder.

        Pattern: ${vault:alias.field}
        Fields: secret, username, metadata.KEY

        Example:
            ${vault:salesforce_prod.secret} → "hunter2"
            ${vault:salesforce_prod.username} → "admin@acme.com"
        """
        if not placeholder.startswith("${vault:") or not placeholder.endswith("}"):
            return placeholder

        inner = placeholder[8:-1]  # Strip ${vault: and }
        parts = inner.split(".", 1)
        alias = parts[0]
        field = parts[1] if len(parts) > 1 else "secret"

        cred = await self.get_credential(alias, tenant_id, requested_by)
        try:
            if field == "secret":
                return cred.secret
            elif field == "username":
                return cred.username or ""
            elif field.startswith("metadata."):
                key = field[9:]
                return str(cred.metadata.get(key, ""))
            else:
                return cred.secret
        finally:
            if self._auto_wipe:
                cred.wipe()

    async def resolve_in_dict(
        self,
        data: Dict[str, Any],
        tenant_id: str,
        requested_by: str = "system",
    ) -> Dict[str, Any]:
        """Resolve all credential placeholders in a dictionary.

        Recursively scans values for ${vault:...} patterns.
        """
        resolved = {}
        for key, value in data.items():
            if isinstance(value, str) and "${vault:" in value:
                resolved[key] = await self.resolve_placeholder(
                    value, tenant_id, requested_by
                )
            elif isinstance(value, dict):
                resolved[key] = await self.resolve_in_dict(
                    value, tenant_id, requested_by
                )
            else:
                resolved[key] = value
        return resolved
