# PLAN_V2.md — Enterprise Features Implementation Plan

> **Version:** 2.0.0
> **Created:** 2026-04-04
> **Target Completion:** 14 weeks
> **Status:** Planning

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Phase 6: Credential Vault & Secret Injection](#3-phase-6-credential-vault--secret-injection)
4. [Phase 7: Audit Trail & Compliance Engine](#4-phase-7-audit-trail--compliance-engine)
5. [Phase 8: Approval Workflows & Governance](#5-phase-8-approval-workflows--governance)
6. [Phase 9: Scheduled & Recurring Workflows](#6-phase-9-scheduled--recurring-workflows)
7. [Phase 10: Data Loss Prevention (DLP)](#7-phase-10-data-loss-prevention-dlp)
8. [Phase 11: Multi-Tenant Task Orchestrator](#8-phase-11-multi-tenant-task-orchestrator)
9. [Phase 12: Workflow Recording & Replay](#9-phase-12-workflow-recording--replay)
10. [Testing Strategy](#10-testing-strategy)
11. [Timeline](#11-timeline)
12. [Dependencies](#12-dependencies)
13. [Risk Assessment](#13-risk-assessment)

---

## 1. Overview

### 1.1 Problem Statement

UI-TARS-desktop (by Bytedance) dominates the open-source browser agent space with a strong vision model and slick desktop app. However, it's built for individual developers — not enterprises. No enterprise will deploy a browser agent that:

- Stores credentials in plaintext config files
- Has no audit trail of what it did
- Can execute destructive actions without approval
- Can't run on a schedule
- Might leak PII through LLM prompts
- Can't serve multiple teams in isolation
- Requires natural language for every repeatable workflow

### 1.2 Strategy

Build features that make b-agent the **enterprise-ready** browser automation platform. These features layer on top of the existing architecture (resilience, multi-agent, skills, API) and are **orthogonal** to UI-TARS-desktop — they don't compete with the vision model, they wrap around it.

### 1.3 Goals

| Goal | Metric |
|------|--------|
| Credential security | Zero plaintext credentials in code, logs, or memory dumps |
| Compliance | SOC2-Type-II-auditable action log for every browser operation |
| Governance | Configurable approval gates for sensitive actions |
| Reliability | Scheduled tasks complete within SLA or alert on failure |
| Data safety | Zero PII leaks through LLM prompt or API response |
| Scalability | 50+ concurrent tenants with isolated execution |
| Usability | Non-technical users can record and replay workflows |

---

## 2. Architecture

### 2.1 New Module Structure

```
browser_agent/
├── security/                    # Phase 6 + 10
│   ├── __init__.py
│   ├── credential_vault.py      # Encrypted credential storage
│   ├── secret_providers.py      # Vault/AWS/Azure integrations
│   ├── crypto.py                # Encryption utilities
│   ├── dlp.py                   # Data Loss Prevention engine
│   ├── pii_detector.py          # PII detection (regex + ML)
│   └── redaction.py             # Data redaction/masking
│
├── compliance/                  # Phase 7
│   ├── __init__.py
│   ├── audit_log.py             # Immutable audit trail
│   ├── audit_store.py           # Storage backends (SQLite, PostgreSQL, S3)
│   ├── data_classifier.py       # Data sensitivity classification
│   ├── chain.py                 # Cryptographic chain (tamper-evidence)
│   └── export.py                # SIEM/export formatters
│
├── governance/                  # Phase 8
│   ├── __init__.py
│   ├── policy_engine.py         # Rule-based policy evaluation
│   ├── approval.py              # Approval workflow manager
│   ├── notifiers.py             # Slack/Teams/Email notification
│   ├── gates.py                 # Pre-action gate implementations
│   └── policy_definitions.py    # Built-in policy templates
│
├── scheduling/                  # Phase 9
│   ├── __init__.py
│   ├── scheduler.py             # Cron-like scheduler
│   ├── recurring_task.py        # Recurring task definitions
│   ├── health_monitor.py        # SLA monitoring & alerting
│   └── calendar.py              # Business hours/calendar support
│
├── orchestration/               # Phase 11
│   ├── __init__.py
│   ├── tenant_manager.py        # Multi-tenant isolation
│   ├── resource_pool.py         # Browser worker pool
│   ├── scheduler_fair.py        # Fair scheduling across tenants
│   ├── quotas.py                # Resource quotas per tenant
│   └── metering.py              # Usage metering & billing hooks
│
├── recording/                   # Phase 12
│   ├── __init__.py
│   ├── recorder.py              # Workflow recording engine
│   ├── player.py                # Workflow replay engine
│   ├── parameterizer.py         # Variable extraction from recordings
│   ├── adaptive_replay.py       # Vision-based self-healing replay
│   └── version_control.py       # Recording version tracking
│
└── api/                         # Updated API layer
    ├── app.py                   # Updated with new endpoints
    ├── models_v2.py             # V2 request/response models
    ├── middleware/
    │   ├── tenant_resolver.py   # Multi-tenant middleware
    │   ├── audit_middleware.py   # Auto-audit all requests
    │   └── dlp_middleware.py     # Scan responses for PII
    └── routes/
        ├── credentials.py       # /credentials/* endpoints
        ├── audit.py             # /audit/* endpoints
        ├── governance.py        # /policies/* endpoints
        ├── scheduling.py        # /schedules/* endpoints
        ├── tenants.py           # /tenants/* endpoints
        └── recordings.py        # /recordings/* endpoints
```

### 2.2 Integration Points

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer (V2)                           │
│  tenant_resolver → audit_middleware → dlp_middleware → routes   │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│                     Orchestration Layer                         │
│  TenantManager → FairScheduler → ResourcePool → QuotaEnforcer  │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│                     Governance Layer                            │
│  PolicyEngine → ApprovalManager → GateEvaluator                │
│  ↕ CredentialVault  ↕ AuditLog  ↕ DLPEngine                   │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│                  Existing Agent Core                            │
│  Supervisor → Planner → Analyzer → Actor → Validator           │
│  Skills → Memory → Resilience → Vision                         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Data Flow

Every task goes through this pipeline:

```
Task Request
  → Tenant Resolution (who is this?)
  → Policy Evaluation (is this allowed?)
  → Approval Gate (does this need sign-off?)
  → Credential Injection (load secrets, if needed)
  → DLP Pre-scan (check goal/params for PII)
  → Task Execution (existing agent core)
      → Pre-action Audit (log what's about to happen)
      → Action Execution
      → Post-action Audit (log what happened)
      → DLP Post-scan (redact extracted data)
  → Audit Finalization (cryptographic chain update)
  → Result Delivery
```

---

## 3. Phase 6: Credential Vault & Secret Injection

**Duration:** 2 weeks (Week 1–2)
**Priority:** 🔴 Critical
**Depends on:** Nothing (foundation for Phase 8)

### 3.1 Objectives

- Store browser automation credentials (usernames, passwords, API keys, cookies, tokens) securely
- Never expose secrets in logs, memory dumps, screenshots, or API responses
- Support external secret managers (HashiCorp Vault, AWS Secrets Manager, Azure Key Vault)
- Enable per-tenant credential scoping

### 3.2 Components

#### 3.2.1 `browser_agent/security/crypto.py`

Cryptographic utilities for the vault.

```python
class CryptoEngine:
    """AES-256-GCM encryption for credential storage."""
    
    def __init__(self, master_key: bytes):
        """
        Args:
            master_key: 32-byte master encryption key.
                        Loaded from CREDS_MASTER_KEY env var or HSM.
        """
    
    def encrypt(self, plaintext: str) -> EncryptedBlob:
        """Encrypt plaintext → {ciphertext, iv, tag, version}"""
    
    def decrypt(self, blob: EncryptedBlob) -> str:
        """Decrypt EncryptedBlob → plaintext"""
    
    def rotate_key(self, new_key: bytes, blobs: List[EncryptedBlob]) -> List[EncryptedBlob]:
        """Re-encrypt all blobs with new master key"""
    
    def derive_key(self, tenant_id: str) -> bytes:
        """Derive tenant-specific key from master key using HKDF"""


@dataclass
class EncryptedBlob:
    ciphertext: bytes
    iv: bytes           # 12-byte nonce
    tag: bytes          # 16-byte auth tag
    version: int = 1    # Key version for rotation
    algorithm: str = "AES-256-GCM"
    
    def to_dict(self) -> dict:
        """Serialize for storage (base64 encoded)"""
    
    @classmethod
    def from_dict(cls, data: dict) -> 'EncryptedBlob':
        """Deserialize from storage"""
```

**Implementation notes:**
- Use `cryptography` library (already in Python ecosystem, no extra deps beyond what's standard)
- AES-256-GCM provides both encryption and authentication
- Key derivation via HKDF-SHA256 with tenant_id as context
- Master key loaded from env var `CREDS_MASTER_KEY` (base64-encoded 32 bytes)

#### 3.2.2 `browser_agent/security/credential_vault.py`

Core credential management.

```python
class CredentialEntry:
    """A single credential record."""
    credential_id: str          # UUID
    alias: str                  # e.g., "salesforce_prod", "sap_finance"
    tenant_id: str              # Owner tenant
    credential_type: CredentialType  # PASSWORD, API_KEY, OAUTH_TOKEN, COOKIE, CERTIFICATE
    username: Optional[str]     # For password-type credentials
    encrypted_secret: EncryptedBlob  # The actual secret (password, key, token)
    metadata: Dict[str, Any]    # Non-sensitive metadata (url, description, tags)
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]   # For time-limited tokens
    last_used_at: Optional[datetime]
    rotation_policy: Optional[RotationPolicy]
    access_count: int = 0
    created_by: str
    last_accessed_by: Optional[str]


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
    ON_USE = "on_use"           # Rotate every N uses
    TIME_BASED = "time_based"   # Rotate every N days
    ON_FAILURE = "on_failure"   # Rotate when authentication fails


class CredentialVault:
    """Encrypted credential storage with access control."""
    
    def __init__(self, crypto: CryptoEngine, store: CredentialStore):
        """
        Args:
            crypto: Encryption engine
            store: Storage backend (SQLite, file, external)
        """
    
    async def store_credential(
        self,
        alias: str,
        tenant_id: str,
        credential_type: CredentialType,
        secret: str,
        username: Optional[str] = None,
        metadata: Optional[Dict] = None,
        expires_at: Optional[datetime] = None,
        rotation_policy: RotationPolicy = RotationPolicy.NONE,
        created_by: str = "system",
    ) -> CredentialEntry:
        """Store a new credential."""
    
    async def get_credential(
        self,
        alias: str,
        tenant_id: str,
        requested_by: str = "system",
    ) -> DecryptedCredential:
        """
        Retrieve and decrypt a credential.
        - Logs access for audit
        - Checks expiry
        - Triggers rotation if policy requires
        - Returns DecryptedCredential with auto-wipe after use
        """
    
    async def list_credentials(
        self,
        tenant_id: str,
    ) -> List[CredentialSummary]:
        """List credentials (without decrypting secrets)."""
    
    async def delete_credential(
        self,
        alias: str,
        tenant_id: str,
        deleted_by: str = "system",
    ) -> bool:
        """Securely delete a credential."""
    
    async def rotate_credential(
        self,
        alias: str,
        tenant_id: str,
        new_secret: str,
        rotated_by: str = "system",
    ) -> CredentialEntry:
        """Rotate credential secret."""
    
    async def check_expiry(self) -> List[ExpiringCredential]:
        """Find credentials approaching expiry."""


class DecryptedCredential:
    """Temporary holder for decrypted credential. Auto-wipes on context exit."""
    
    def __init__(self, entry: CredentialEntry, secret: str):
        self._entry = entry
        self._secret = secret
        self._wiped = False
    
    @property
    def username(self) -> Optional[str]:
        return self._entry.username
    
    @property
    def secret(self) -> str:
        if self._wiped:
            raise ValueError("Credential has been wiped")
        return self._secret
    
    @property
    def metadata(self) -> Dict[str, Any]:
        return self._entry.metadata
    
    def wipe(self):
        """Overwrite secret in memory with zeros."""
        # Use ctypes to zero the string's memory
        self._secret = "0" * len(self._secret)
        self._wiped = True
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.wipe()
    
    def __del__(self):
        if not self._wiped:
            self.wipe()


class CredentialStore(ABC):
    """Abstract storage backend for credentials."""
    
    @abstractmethod
    async def save(self, entry: CredentialEntry) -> str:
        """Save encrypted credential. Returns credential_id."""
    
    @abstractmethod
    async def load(self, alias: str, tenant_id: str) -> Optional[CredentialEntry]:
        """Load encrypted credential by alias + tenant."""
    
    @abstractmethod
    async def delete(self, alias: str, tenant_id: str) -> bool:
        """Delete credential."""
    
    @abstractmethod
    async def list_aliases(self, tenant_id: str) -> List[str]:
        """List credential aliases for tenant."""
    
    @abstractmethod
    async def update(self, entry: CredentialEntry) -> bool:
        """Update existing credential."""


class FileCredentialStore(CredentialStore):
    """File-based encrypted credential storage (default)."""
    # Stores in .credentials/ directory as JSON files
    # Each file: one tenant's credentials, encrypted at rest


class SQLiteCredentialStore(CredentialStore):
    """SQLite-based credential storage for production deployments."""
    # Table: credentials (id, alias, tenant_id, type, encrypted_blob, metadata, timestamps)
```

#### 3.2.3 `browser_agent/security/secret_providers.py`

External secret manager integrations.

```python
class SecretProvider(ABC):
    """Interface for external secret management systems."""
    
    @abstractmethod
    async def get_secret(self, path: str) -> Dict[str, str]:
        """Fetch secret from external provider."""
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check connectivity to provider."""


class HashiCorpVaultProvider(SecretProvider):
    """HashiCorp Vault integration via hvac library."""
    # KV v2 secret engine support
    # AppRole + Kubernetes auth methods
    # Secret versioning


class AWSSecretsManagerProvider(SecretProvider):
    """AWS Secrets Manager integration via boto3."""
    # Automatic rotation support
    # Cross-region secret replication


class AzureKeyVaultProvider(SecretProvider):
    """Azure Key Vault integration via azure-keyvault."""
    # Managed identity support
    # Certificate-based auth


class EnvironmentProvider(SecretProvider):
    """Load secrets from environment variables (dev/local mode)."""
    # Pattern: CREDENTIAL_{ALIAS}_USERNAME, CREDENTIAL_{ALIAS}_SECRET


class ChainedProvider(SecretProvider):
    """Try multiple providers in order (e.g., Vault → Env fallback)."""
    providers: List[SecretProvider]
```

#### 3.2.4 Integration with Agent Core

```python
# In browser_agent/agents/actor.py — extended action handling

class ActorAgent:
    def __init__(self, ..., credential_vault: Optional[CredentialVault] = None):
        self._vault = credential_vault
    
    async def _inject_credentials(self, action: Dict, context: Dict) -> Dict:
        """
        Replace credential placeholders in action params.
        Pattern: ${vault:alias.field}
        Example: ${vault:salesforce_prod.username} → "admin@corp.com"
        """
        # Scan action params for ${vault:...} patterns
        # Resolve each via vault
        # Inject resolved values
        # Log credential access to audit trail
        # Return modified action (never store resolved values)
```

```python
# In browser_agent/agent.py — top-level integration

class BrowserAgent:
    def __init__(self, config, credential_vault=None, audit_log=None, ...):
        self.credential_vault = credential_vault or CredentialVault.from_config(config)
    
    async def execute_task(self, goal, start_url=None, credential_aliases=None, ...):
        """
        Extended task execution with credential support.
        
        Args:
            credential_aliases: Dict mapping field names to vault aliases
                e.g., {"username": "salesforce_prod", "password": "salesforce_prod"}
        """
```

### 3.3 API Endpoints

```
POST   /credentials                    # Store new credential
GET    /credentials                    # List credentials (aliases only)
GET    /credentials/{alias}            # Get credential metadata (never returns secret)
PUT    /credentials/{alias}            # Update credential
DELETE /credentials/{alias}            # Delete credential
POST   /credentials/{alias}/rotate     # Rotate credential secret
GET    /credentials/{alias}/access-log  # Get access history for credential
POST   /credentials/test-connection    # Test a credential against a URL
```

### 3.4 Configuration

```yaml
# config.yaml additions
security:
  credential_vault:
    enabled: true
    master_key_env: CREDS_MASTER_KEY     # Env var name for master key
    store_type: file                      # file | sqlite | vault | aws | azure
    store_path: .credentials              # For file store
    auto_wipe: true                       # Wipe secrets from memory after use
    rotation_check_interval: 3600         # Check expiry every hour
    expiry_warning_days: 7                # Warn N days before expiry
    
    # External provider config (only one active)
    hashicorp_vault:
      url: http://vault:8200
      auth_method: approle                # approle | kubernetes | token
      role_id: ${VAULT_ROLE_ID}
      secret_id: ${VAULT_SECRET_ID}
      mount_point: secret
    
    aws_secrets_manager:
      region: us-east-1
      access_key_id: ${AWS_ACCESS_KEY_ID}
      secret_access_key: ${AWS_SECRET_ACCESS_KEY}
    
    azure_key_vault:
      vault_url: https://myvault.vault.azure.net/
      tenant_id: ${AZURE_TENANT_ID}
      client_id: ${AZURE_CLIENT_ID}
      client_secret: ${AZURE_CLIENT_SECRET}
```

### 3.5 Tests

```
tests/test_security/
├── test_crypto.py              # 15 tests — encryption, decryption, key rotation, derivation
├── test_credential_vault.py    # 20 tests — store, get, delete, rotate, expiry, wipe
├── test_secret_providers.py    # 12 tests — each provider, chained provider
├── test_credential_injection.py # 10 tests — placeholder resolution, auto-wipe
└── test_credential_api.py      # 15 tests — API endpoint tests
```

### 3.6 Tasks

| # | Task | Est. | Status |
|---|------|------|--------|
| 6.1 | Implement `crypto.py` — AES-256-GCM encryption, key derivation, rotation | 1d | [x] |
| 6.2 | Implement `CredentialEntry`, `DecryptedCredential` dataclasses | 0.5d | [x] |
| 6.3 | Implement `CredentialVault` core — store, get, delete, rotate | 1.5d | [x] |
| 6.4 | Implement `FileCredentialStore` | 0.5d | [x] |
| 6.5 | Implement `SQLiteCredentialStore` | 0.5d | [x] |
| 6.6 | Implement `EnvironmentProvider` and `ChainedProvider` | 0.5d | [x] |
| 6.7 | Implement `HashiCorpVaultProvider` | 0.5d | [x] |
| 6.8 | Implement `AWSSecretsManagerProvider` | 0.5d | [x] |
| 6.9 | Implement `AzureKeyVaultProvider` | 0.5d | [x] |
| 6.10 | Integrate credential injection into `ActorAgent` | 1d | [x] |
| 6.11 | Integrate credential vault into `BrowserAgent` | 0.5d | [x] |
| 6.12 | Add credential API endpoints | 1d | [x] |
| 6.13 | Write config schema for security section | 0.5d | [x] |
| 6.14 | Write all tests | 2d | [x] |
| 6.15 | Integration test: full credential workflow | 0.5d | [x] |

**Total: ~11 days**

---

## 4. Phase 7: Audit Trail & Compliance Engine

**Duration:** 2 weeks (Week 2–4, overlaps with Phase 6)
**Priority:** 🔴 Critical
**Depends on:** Phase 6 (credential vault logs into audit trail)

### 4.1 Objectives

- Record every action the agent takes in an immutable, tamper-evident log
- Enable SOC2, HIPAA, GDPR compliance reporting
- Support right-to-erasure requests
- Export to standard SIEM formats

### 4.2 Components

#### 4.2.1 `browser_agent/compliance/audit_log.py`

```python
class AuditEventType(Enum):
    # Task lifecycle
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    
    # Actions
    ACTION_EXECUTED = "action.executed"
    ACTION_SUCCEEDED = "action.succeeded"
    ACTION_FAILED = "action.failed"
    ACTION_RETRIED = "action.retried"
    ACTION_BLOCKED = "action.blocked"          # Blocked by policy
    
    # Credential access
    CREDENTIAL_ACCESSED = "credential.accessed"
    CREDENTIAL_ROTATED = "credential.rotated"
    CREDENTIAL_EXPIRED = "credential.expired"
    
    # Governance
    POLICY_EVALUATED = "policy.evaluated"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_DENIED = "approval.denied"
    
    # Data
    DATA_EXTRACTED = "data.extracted"
    DATA_CLASSIFIED = "data.classified"
    DATA_REDACTED = "data.redacted"
    DATA_EXPORTED = "data.exported"
    DATA_DELETED = "data.deleted"              # Right to erasure
    
    # System
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    BROWSER_OPENED = "browser.opened"
    BROWSER_CLOSED = "browser.closed"
    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_RESTORED = "checkpoint.restored"
    RECOVERY_TRIGGERED = "recovery.triggered"


class AuditEvent:
    """A single audit trail entry."""
    event_id: str                  # UUID
    timestamp: datetime            # UTC, microsecond precision
    event_type: AuditEventType
    tenant_id: str
    user_id: str                   # Who initiated the task
    task_id: Optional[str]
    step_index: Optional[int]
    
    # What happened
    action_type: Optional[str]     # e.g., "click", "type_text", "navigate"
    target_url: Optional[str]      # URL being acted upon
    target_element: Optional[str]  # Element description
    parameters: Dict[str, Any]     # Action parameters (secrets redacted)
    
    # Outcome
    outcome: str                   # "success", "failure", "blocked", "redacted"
    error_message: Optional[str]
    
    # Data classification
    data_sensitivity: Optional[SensitivityLevel]
    data_categories: List[str]     # e.g., ["pii", "financial"]
    
    # Cryptographic chain
    previous_hash: str             # Hash of previous event (chain)
    event_hash: str                # Hash of this event
    chain_signature: Optional[str] # HMAC of event_hash with chain key
    
    # Context
    session_id: Optional[str]
    agent_id: Optional[str]        # Which agent performed the action
    ip_address: Optional[str]
    user_agent: Optional[str]
    
    # Screenshots
    screenshot_hash: Optional[str] # SHA-256 of screenshot (not stored inline)
    screenshot_path: Optional[str] # Path to stored screenshot


class SensitivityLevel(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class AuditLog:
    """Immutable, append-only audit trail."""
    
    def __init__(self, store: AuditStore, chain: AuditChain):
        """
        Args:
            store: Storage backend for events
            chain: Cryptographic chain for tamper-evidence
        """
    
    async def record(self, event: AuditEvent) -> AuditEvent:
        """
        Record an audit event.
        - Computes hash chain
        - Signs event
        - Persists to store
        - Returns recorded event (with hash populated)
        """
    
    async def query(
        self,
        tenant_id: Optional[str] = None,
        event_types: Optional[List[AuditEventType]] = None,
        task_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        sensitivity: Optional[SensitivityLevel] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """Query audit events with filters."""
    
    async def verify_chain(self, tenant_id: str) -> ChainVerificationResult:
        """
        Verify integrity of the entire audit chain.
        - Recomputes hashes
        - Verifies signatures
        - Reports any tampered entries
        """
    
    async def export(
        self,
        format: str,  # "json", "csv", "cef" (Common Event Format), "syslog"
        **query_params,
    ) -> str:
        """Export audit events in standard format."""
    
    async def delete_data_for_subject(
        self,
        tenant_id: str,
        subject_identifier: str,
        requested_by: str,
    ) -> DataDeletionRecord:
        """
        GDPR right-to-erasure.
        - Finds all events referencing subject
        - Redacts identifying information
        - Records deletion event in audit trail
        - Returns deletion record
        """
    
    async def get_task_timeline(self, task_id: str) -> TaskTimeline:
        """Get full timeline of events for a task."""
    
    async def generate_compliance_report(
        self,
        framework: str,  # "soc2", "hipaa", "gdpr"
        start_date: datetime,
        end_date: datetime,
        tenant_id: str,
    ) -> ComplianceReport:
        """Generate compliance report for a time period."""
```

#### 4.2.2 `browser_agent/compliance/chain.py`

```python
class AuditChain:
    """Cryptographic hash chain for tamper-evident audit log."""
    
    def __init__(self, signing_key: bytes):
        """
        Args:
            signing_key: HMAC-SHA256 key for chain signatures
        """
    
    def compute_hash(self, event: AuditEvent) -> str:
        """Compute SHA-256 hash of event fields."""
    
    def link(self, event: AuditEvent, previous_hash: str) -> AuditEvent:
        """
        Link event to chain.
        - Sets previous_hash
        - Computes event_hash
        - Signs with HMAC
        """
    
    def verify(self, events: List[AuditEvent]) -> ChainVerificationResult:
        """
        Verify entire chain.
        - Check each event's hash
        - Check previous_hash linkage
        - Verify HMAC signatures
        """
    
    def seal(self, events: List[AuditEvent]) -> ChainSeal:
        """
        Create periodic seal (like a blockchain checkpoint).
        - Merkle root of all events since last seal
        - Signed seal hash
        """


@dataclass
class ChainVerificationResult:
    total_events: int
    verified_events: int
    tampered_events: List[TamperedEvent]
    missing_events: List[MissingEvent]
    is_valid: bool
    verification_time: float


@dataclass
class ChainSeal:
    seal_id: str
    merkle_root: str
    event_count: int
    first_event_id: str
    last_event_id: str
    signature: str
    created_at: datetime
```

#### 4.2.3 `browser_agent/compliance/audit_store.py`

```python
class AuditStore(ABC):
    @abstractmethod
    async def append(self, event: AuditEvent) -> str: ...
    
    @abstractmethod
    async def query(self, filters: AuditFilter) -> List[AuditEvent]: ...
    
    @abstractmethod
    async def get_last_event(self, tenant_id: str) -> Optional[AuditEvent]: ...
    
    @abstractmethod
    async def count(self, filters: AuditFilter) -> int: ...


class SQLiteAuditStore(AuditStore):
    """SQLite storage for single-node deployments."""
    # Table: audit_events (all fields + JSON for parameters)
    # Indexes: tenant_id, task_id, timestamp, event_type


class FileAuditStore(AuditStore):
    """Append-only JSONL file for simple deployments."""
    # One file per day: audit_2026-04-04.jsonl
    # Compaction: merge old files into compressed archives


class PostgresAuditStore(AuditStore):
    """PostgreSQL storage for production multi-tenant deployments."""
    # Partitioned by tenant_id and month
    # Full-text search on parameters
```

#### 4.2.4 `browser_agent/compliance/data_classifier.py`

```python
class DataClassifier:
    """Classify extracted data by sensitivity level."""
    
    def classify(self, data: Any, context: Dict) -> ClassificationResult:
        """
        Classify data based on:
        - Content patterns (PII, PHI, financial)
        - Source URL (internal vs external, admin panel vs public)
        - Data type (names, emails, prices, IDs)
        - User-defined rules
        """
    
    def classify_field(self, field_name: str, field_value: Any) -> FieldClassification:
        """Classify a single data field."""
    
    def classify_page(self, url: str, page_content: str) -> PageClassification:
        """Classify an entire page's data sensitivity."""


@dataclass
class ClassificationResult:
    sensitivity: SensitivityLevel
    categories: List[DataCategory]
    pii_fields: List[str]
    phi_fields: List[str]
    financial_fields: List[str]
    confidence: float
    rules_matched: List[str]


class DataCategory(Enum):
    PII = "pii"                   # Personally Identifiable Information
    PHI = "phi"                   # Protected Health Information
    FINANCIAL = "financial"       # Financial data (CC, bank accounts)
    CREDENTIALS = "credentials"   # Usernames, passwords, tokens
    INTERNAL = "internal"         # Internal business data
    PUBLIC = "public"             # Publicly available data
    CONFIDENTIAL = "confidential" # Confidential business data
```

#### 4.2.5 `browser_agent/compliance/export.py`

```python
class AuditExporter:
    """Export audit events to external systems."""
    
    async def to_cef(self, events: List[AuditEvent]) -> str:
        """Export in Common Event Format (ArcSight, Splunk)."""
    
    async def to_syslog(self, events: List[AuditEvent]) -> str:
        """Export in syslog format."""
    
    async def to_csv(self, events: List[AuditEvent]) -> str:
        """Export as CSV."""
    
    async def to_json(self, events: List[AuditEvent]) -> str:
        """Export as JSON array."""
    
    async def to_ocsf(self, events: List[AuditEvent]) -> str:
        """Export in Open Cybersecurity Schema Framework."""


class SIEMIntegration:
    """Push audit events to SIEM in real-time."""
    
    async def push_to_splunk(self, event: AuditEvent, hec_url: str, token: str):
        """Push to Splunk HTTP Event Collector."""
    
    async def push_to_datadog(self, event: AuditEvent, api_key: str):
        """Push to Datadog Logs API."""
    
    async def push_to_elk(self, event: AuditEvent, elasticsearch_url: str):
        """Push to Elasticsearch."""
```

### 4.3 Integration Points

```python
# Automatic audit logging in ActionExecutor
class ActionExecutor:
    def __init__(self, ..., audit_log: Optional[AuditLog] = None):
        self._audit = audit_log
    
    async def execute_action(self, action, context):
        # Pre-action audit
        await self._audit.record(AuditEvent(
            event_type=AuditEventType.ACTION_EXECUTED,
            action_type=action.type,
            target_url=context.page.url,
            ...
        ))
        
        result = await self._execute(action, context)
        
        # Post-action audit
        await self._audit.record(AuditEvent(
            event_type=AuditEventType.ACTION_SUCCEEDED if result.success else AuditEventType.ACTION_FAILED,
            ...
        ))
        
        return result
```

```python
# API middleware for automatic request auditing
class AuditMiddleware:
    async def __call__(self, request, call_next):
        event = create_request_audit_event(request)
        response = await call_next(request)
        event.outcome = "success"
        await self.audit_log.record(event)
        return response
```

### 4.4 API Endpoints

```
GET    /audit/events                   # Query audit events with filters
GET    /audit/events/{event_id}        # Get specific event
GET    /audit/tasks/{task_id}/timeline # Get task timeline
POST   /audit/verify-chain             # Verify chain integrity
GET    /audit/export                   # Export events (format param)
GET    /audit/compliance-report        # Generate compliance report
POST   /audit/data-deletion            # GDPR right-to-erasure
GET    /audit/statistics               # Audit statistics (event counts, types)
```

### 4.5 Configuration

```yaml
compliance:
  audit_log:
    enabled: true
    store_type: sqlite                   # sqlite | file | postgres
    store_path: .audit/audit.db          # For sqlite/file
    chain_enabled: true                  # Enable cryptographic chain
    chain_key_env: AUDIT_CHAIN_KEY       # HMAC signing key env var
    seal_interval: 3600                  # Create chain seal every hour
    screenshot_storage: .audit/screenshots
    retention_days: 365                  # Keep audit logs for 1 year
    auto_classify_data: true             # Classify extracted data sensitivity
    
    siem:
      enabled: false
      type: splunk                      # splunk | datadog | elk | none
      url: ${SIEM_URL}
      api_key: ${SIEM_API_KEY}
      batch_size: 100                   # Batch events before pushing
      flush_interval: 30                # Flush batch every N seconds
```

### 4.6 Tests

```
tests/test_compliance/
├── test_audit_log.py            # 20 tests — record, query, delete, timeline
├── test_chain.py                # 15 tests — hash computation, linking, verification, sealing
├── test_audit_store.py          # 12 tests — SQLite store, file store, queries
├── test_data_classifier.py      # 15 tests — PII, PHI, financial, URL-based classification
├── test_export.py               # 10 tests — CEF, syslog, CSV, JSON export
├── test_siem.py                 # 8 tests — Splunk, Datadog, ELK push (mocked)
├── test_compliance_report.py    # 8 tests — SOC2, HIPAA, GDPR reports
└── test_audit_api.py            # 15 tests — API endpoint tests
```

### 4.7 Tasks

| # | Task | Est. | Status |
|---|------|------|--------|
| 7.1 | Implement `AuditEvent`, `AuditEventType`, `SensitivityLevel` dataclasses | 0.5d | [x] |
| 7.2 | Implement `AuditChain` — hash computation, linking, verification, sealing | 1.5d | [x] |
| 7.3 | Implement `AuditLog` core — record, query, delete_data_for_subject | 1.5d | [x] |
| 7.4 | Implement `SQLiteAuditStore` | 1d | [x] |
| 7.5 | Implement `FileAuditStore` | 0.5d | [x] |
| 7.6 | Implement `DataClassifier` | 1d | [x] |
| 7.7 | Implement `AuditExporter` (CEF, syslog, CSV, JSON) | 1d | [x] |
| 7.8 | Implement `SIEMIntegration` (Splunk, Datadog, ELK) | 1d | [x] |
| 7.9 | Implement compliance report generation | 1d | [x] |
| 7.10 | Integrate audit logging into `ActionExecutor` | 0.5d | [x] |
| 7.11 | Integrate audit logging into `BrowserAgent` lifecycle | 0.5d | [x] |
| 7.12 | Implement `AuditMiddleware` for API | 0.5d | [x] |
| 7.13 | Add audit API endpoints | 1d | [x] |
| 7.14 | Write config schema for compliance section | 0.5d | [x] |
| 7.15 | Write all tests | 2.5d | [x] |

**Total: ~14 days**

---

## 5. Phase 8: Approval Workflows & Governance

**Duration:** 2 weeks (Week 4–6)
**Priority:** 🟡 High
**Depends on:** Phase 6 (credential vault), Phase 7 (audit trail for approval events)

### 5.1 Objectives

- Define policies that gate certain actions based on URL, action type, data sensitivity
- Route approval requests to humans via Slack/Teams/Email
- Pause workflow execution at gates, resume on approval
- Full audit trail of all approval decisions

### 5.2 Components

#### 5.2.1 `browser_agent/governance/policy_engine.py`

```python
class PolicyEffect(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyCondition:
    """A single condition in a policy rule."""
    field: str                    # "target_url", "action_type", "sensitivity", "tenant_id"
    operator: str                 # "equals", "contains", "matches", "in", "greater_than"
    value: Any                    # Expected value
    
    def evaluate(self, context: Dict) -> bool:
        """Evaluate condition against context."""


class PolicyRule:
    """A governance policy rule."""
    rule_id: str
    name: str
    description: str
    effect: PolicyEffect
    conditions: List[PolicyCondition]     # All must match (AND logic)
    approval_config: Optional[ApprovalConfig]  # Required if effect = REQUIRE_APPROVAL
    priority: int = 0                      # Higher priority rules evaluated first
    enabled: bool = True
    tenant_id: Optional[str]               # None = global policy
    tags: List[str] = []


class ApprovalConfig:
    """Configuration for an approval gate."""
    approval_type: str                      # "single", "quorum", "escalation"
    approvers: List[str]                    # User IDs or roles
    timeout_seconds: int = 3600             # 1 hour default
    auto_deny_on_timeout: bool = True
    escalation_approvers: Optional[List[str]]
    escalation_after_seconds: Optional[int]
    notification_channels: List[str]        # ["slack: #approvals", "email"]
    message_template: Optional[str]         # Custom notification message


class PolicyEngine:
    """Evaluate governance policies for actions."""
    
    def __init__(self, rules: List[PolicyRule], audit_log: AuditLog):
        self._rules = sorted(rules, key=lambda r: -r.priority)
        self._audit = audit_log
    
    async def evaluate(self, context: PolicyContext) -> PolicyDecision:
        """
        Evaluate all applicable rules against context.
        
        Returns the highest-priority matching rule's effect.
        If no rules match, default effect is ALLOW (open by default).
        
        Records policy evaluation in audit trail.
        """
    
    async def add_rule(self, rule: PolicyRule) -> str:
        """Add a new policy rule."""
    
    async def remove_rule(self, rule_id: str) -> bool:
        """Remove a policy rule."""
    
    async def list_rules(self, tenant_id: Optional[str] = None) -> List[PolicyRule]:
        """List all rules, optionally filtered by tenant."""
    
    async def dry_run(self, context: PolicyContext) -> PolicyDecision:
        """Evaluate without enforcing (for testing policies)."""


@dataclass
class PolicyContext:
    """Context for policy evaluation."""
    action_type: str
    target_url: str
    target_element: Optional[str]
    parameters: Dict[str, Any]
    tenant_id: str
    user_id: str
    task_id: str
    data_sensitivity: Optional[SensitivityLevel]
    credential_alias: Optional[str]
    extracted_data_preview: Optional[str]


@dataclass
class PolicyDecision:
    effect: PolicyEffect
    matched_rule: Optional[PolicyRule]
    reason: str
    requires_approval: bool
    approval_config: Optional[ApprovalConfig]
```

#### 5.2.2 `browser_agent/governance/approval.py`

```python
class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


class ApprovalRequest:
    request_id: str
    task_id: str
    step_index: int
    rule_id: str
    context: PolicyContext
    status: ApprovalStatus
    requested_at: datetime
    requested_by: str
    approvers: List[str]
    approval_config: ApprovalConfig
    expires_at: datetime
    
    # State snapshot for resumption
    checkpoint_id: str             # Checkpoint to restore on approval
    browser_state: Dict            # Browser state at gate
    
    # Resolution
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    resolution_note: Optional[str]
    
    # Escalation
    escalated_at: Optional[datetime]
    escalation_level: int = 0


class ApprovalManager:
    """Manage approval workflows."""
    
    def __init__(
        self,
        audit_log: AuditLog,
        notifiers: List[Notifier],
        store: ApprovalStore,
    ): ...
    
    async def request_approval(
        self,
        context: PolicyContext,
        rule: PolicyRule,
        checkpoint_id: str,
        browser_state: Dict,
    ) -> ApprovalRequest:
        """
        Create approval request, notify approvers, return request.
        """
    
    async def approve(
        self,
        request_id: str,
        approver: str,
        note: Optional[str] = None,
    ) -> ApprovalRequest:
        """Approve a pending request. Records in audit trail."""
    
    async def deny(
        self,
        request_id: str,
        approver: str,
        note: Optional[str] = None,
    ) -> ApprovalRequest:
        """Deny a pending request. Records in audit trail."""
    
    async def check_expired(self) -> List[ApprovalRequest]:
        """Check for expired requests, auto-deny if configured."""
    
    async def get_pending(self, approver: Optional[str] = None) -> List[ApprovalRequest]:
        """Get pending approval requests."""
    
    async def wait_for_approval(
        self,
        request_id: str,
        timeout: Optional[float] = None,
    ) -> ApprovalRequest:
        """
        Block until approval is resolved.
        Used by the workflow engine to pause execution at gates.
        """
```

#### 5.2.3 `browser_agent/governance/notifiers.py`

```python
class Notifier(ABC):
    @abstractmethod
    async def send_approval_request(self, request: ApprovalRequest) -> bool: ...
    
    @abstractmethod
    async def send_resolution(self, request: ApprovalRequest) -> bool: ...


class SlackNotifier(Notifier):
    """Slack integration for approval notifications."""
    # Sends interactive message with Approve/Deny buttons
    # Handles Slack interaction webhook for responses
    # Supports channels and DMs
    
    webhook_url: str
    channel: Optional[str]
    approver_channel_mapping: Dict[str, str]


class TeamsNotifier(Notifier):
    """Microsoft Teams integration."""
    # Adaptive Card with action buttons
    # Teams webhook connector
    
    webhook_url: str


class EmailNotifier(Notifier):
    """Email notifications."""
    # HTML email with approval links
    # Links point back to API endpoints
    
    smtp_host: str
    smtp_port: int
    from_address: str
    approver_email_mapping: Dict[str, str]


class WebhookNotifier(Notifier):
    """Generic webhook for custom integrations."""
    # POST JSON payload to configured URL
    
    url: str
    headers: Dict[str, str]
    secret: Optional[str]  # For HMAC signing


class CompositeNotifier(Notifier):
    """Send to multiple notifiers simultaneously."""
    notifiers: List[Notifier]
```

#### 5.2.4 `browser_agent/governance/gates.py`

Pre-built gate implementations for common scenarios.

```python
class Gate:
    """Base class for approval gates."""
    
    @abstractmethod
    def get_rules(self) -> List[PolicyRule]:
        """Return policy rules for this gate."""


class ProductionURLGate(Gate):
    """Require approval for actions on production URLs."""
    # Rules: if target_url matches production patterns → REQUIRE_APPROVAL
    patterns: List[str]  # e.g., ["prod.salesforce.com", "admin.internal.com"]


class DestructiveActionGate(Gate):
    """Require approval for delete, submit, and bulk operations."""
    # Rules: if action_type in ["click"] and target matches delete/submit → REQUIRE_APPROVAL


class SensitiveDataGate(Gate):
    """Require approval when extracting CONFIDENTIAL or RESTRICTED data."""
    # Rules: if data_sensitivity >= CONFIDENTIAL → REQUIRE_APPROVAL


class FinancialTransactionGate(Gate):
    """Require approval for any action involving financial amounts."""
    # Rules: if parameters contain financial data → REQUIRE_APPROVAL


class ExternalSiteGate(Gate):
    """Require approval for navigating to non-whitelisted domains."""
    # Rules: if target_url not in allowed_domains → REQUIRE_APPROVAL
    allowed_domains: List[str]
```

#### 5.2.5 `browser_agent/governance/policy_definitions.py`

```python
class PolicyTemplates:
    """Built-in policy templates for common enterprise scenarios."""
    
    @staticmethod
    def production_only_approve(production_patterns: List[str], approvers: List[str]) -> List[PolicyRule]:
        """All actions on production systems require approval."""
    
    @staticmethod
    def data_extraction_guard(sensitivity_threshold: SensitivityLevel, approvers: List[str]) -> List[PolicyRule]:
        """Guard against extracting sensitive data without approval."""
    
    @staticmethod
    def cost_control(max_daily_tasks: int, approvers: List[str]) -> List[PolicyRule]:
        """Require approval if daily task count exceeds threshold."""
    
    @staticmethod
    def after_hours_block(allowed_hours: Tuple[int, int]) -> List[PolicyRule]:
        """Block non-urgent tasks outside business hours."""
    
    @staticmethod
    def credential_use_approve(sensitive_aliases: List[str], approvers: List[str]) -> List[PolicyRule]:
        """Require approval when using certain credentials."""
    
    @staticmethod
    def compliance_full() -> List[PolicyRule]:
        """Full compliance mode: approve everything, log everything."""
        # All actions → REQUIRE_APPROVAL
        # Useful for initial deployment / auditing phase
```

### 5.3 Integration with Agent Core

```python
# In browser_agent/agent.py

class BrowserAgent:
    def __init__(self, config, ..., policy_engine=None, approval_manager=None):
        self.policy_engine = policy_engine
        self.approval_manager = approval_manager
    
    async def _execute_with_governance(self, action, context):
        """Execute action with governance checks."""
        
        # Build policy context
        policy_ctx = PolicyContext(
            action_type=action.type,
            target_url=context.page.url,
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            ...
        )
        
        # Evaluate policies
        decision = await self.policy_engine.evaluate(policy_ctx)
        
        if decision.effect == PolicyEffect.DENY:
            raise ActionBlockedError(decision.reason)
        
        if decision.effect == PolicyEffect.REQUIRE_APPROVAL:
            # Create checkpoint for resumption
            checkpoint = await self.checkpoint_manager.create_checkpoint(...)
            
            # Request approval
            request = await self.approval_manager.request_approval(
                context=policy_ctx,
                rule=decision.matched_rule,
                checkpoint_id=checkpoint.id,
                browser_state=await self.browser.get_state(),
            )
            
            # Wait for approval (blocking)
            resolved = await self.approval_manager.wait_for_approval(request.request_id)
            
            if resolved.status == ApprovalStatus.DENIED:
                raise ApprovalDeniedError(resolved.resolution_note)
            
            # Restore state and continue
            await self.checkpoint_manager.restore_checkpoint(context.page, checkpoint.id)
        
        # Execute action
        return await self._execute_action(action, context)
```

### 5.4 API Endpoints

```
GET    /policies/rules                     # List policy rules
POST   /policies/rules                     # Create policy rule
PUT    /policies/rules/{rule_id}           # Update policy rule
DELETE /policies/rules/{rule_id}           # Delete policy rule
POST   /policies/dry-run                   # Test policy evaluation without enforcing

GET    /approvals/pending                  # List pending approvals
POST   /approvals/{request_id}/approve     # Approve request
POST   /approvals/{request_id}/deny        # Deny request
GET    /approvals/{request_id}             # Get approval details
GET    /approvals/history                  # Get approval history
```

### 5.5 Configuration

```yaml
governance:
  policy_engine:
    enabled: true
    default_effect: allow                  # allow | deny (when no rules match)
    evaluation_mode: strict                # strict (deny on error) | permissive (allow on error)
    
  approval:
    store_type: sqlite                     # sqlite | file | postgres
    store_path: .governance/approvals.db
    default_timeout: 3600                  # 1 hour
    auto_deny_on_timeout: true
    escalation_enabled: true
    
  notifiers:
    slack:
      enabled: false
      webhook_url: ${SLACK_WEBHOOK_URL}
      channel: "#bot-approvals"
    
    teams:
      enabled: false
      webhook_url: ${TEAMS_WEBHOOK_URL}
    
    email:
      enabled: false
      smtp_host: smtp.corp.com
      smtp_port: 587
      from_address: bot@corp.com
      approver_mapping:
        manager@corp.com: "manager_team_a"
    
    webhook:
      enabled: false
      url: https://internal.corp.com/approval-webhook
      secret: ${WEBHOOK_SECRET}
  
  gates:
    production_url_gate:
      enabled: true
      patterns:
        - "prod.salesforce.com"
        - "admin.internal.com/*"
      approvers: ["manager@corp.com"]
    
    destructive_action_gate:
      enabled: true
      approvers: ["manager@corp.com", "security@corp.com"]
    
    sensitive_data_gate:
      enabled: true
      threshold: confidential
      approvers: ["dpo@corp.com"]
```

### 5.6 Tests

```
tests/test_governance/
├── test_policy_engine.py         # 18 tests — rule evaluation, priority, conditions
├── test_approval.py              # 15 tests — request, approve, deny, expire, escalate
├── test_notifiers.py             # 12 tests — Slack, Teams, Email, Webhook (mocked)
├── test_gates.py                 # 10 tests — each built-in gate
├── test_policy_templates.py      # 8 tests — template generation
├── test_governance_integration.py # 10 tests — full flow with agent
└── test_governance_api.py        # 15 tests — API endpoints
```

### 5.7 Tasks

| # | Task | Est. | Status |
|---|------|------|--------|
| 8.1 | Implement `PolicyCondition`, `PolicyRule`, `PolicyContext` dataclasses | 0.5d | [x] |
| 8.2 | Implement `PolicyEngine` — evaluate, add/remove rules, dry-run | 1.5d | [x] |
| 8.3 | Implement `ApprovalConfig`, `ApprovalRequest`, `ApprovalStatus` | 0.5d | [x] |
| 8.4 | Implement `ApprovalManager` — request, approve, deny, wait, escalate | 2d | [x] |
| 8.5 | Implement `SlackNotifier` | 1d | [x] |
| 8.6 | Implement `TeamsNotifier` | 0.5d | [x] |
| 8.7 | Implement `EmailNotifier` | 0.5d | [x] |
| 8.8 | Implement `WebhookNotifier` | 0.5d | [x] |
| 8.9 | Implement built-in gates (5 gates) | 1d | [x] |
| 8.10 | Implement `PolicyTemplates` | 0.5d | [x] |
| 8.11 | Integrate governance into `BrowserAgent._execute_with_governance` | 1.5d | [x] |
| 8.12 | Add governance API endpoints | 1d | [x] |
| 8.13 | Write config schema | 0.5d | [x] |
| 8.14 | Write all tests | 2.5d | [x] |

**Total: ~13 days**

---

## 6. Phase 9: Scheduled & Recurring Workflows

**Duration:** 1.5 weeks (Week 6–7)
**Priority:** 🟡 High
**Depends on:** Phase 7 (audit trail for schedule events)

### 6.1 Objectives

- Define recurring browser automation tasks with cron-like schedules
- Resume from checkpoints if a scheduled run fails
- Monitor scheduled task health and alert on missed runs
- Support business-hour-only execution

### 6.2 Components

#### 6.2.1 `browser_agent/scheduling/recurring_task.py`

```python
class RecurringTask:
    task_id: str
    name: str
    description: str
    tenant_id: str
    created_by: str
    
    # Schedule
    schedule: CronSchedule                  # Cron expression + timezone
    enabled: bool = True
    next_run: Optional[datetime]
    last_run: Optional[datetime]
    
    # Task definition
    goal: str                               # Natural language goal
    start_url: Optional[str]
    max_steps: int = 20
    timeout: float = 300.0
    
    # Credential aliases
    credential_aliases: Optional[Dict[str, str]]
    
    # Checkpoint
    checkpoint_on_complete: bool = True     # Save checkpoint after success
    resume_from_checkpoint: bool = True     # Resume from last checkpoint on failure
    
    # Notifications
    notify_on_success: List[str]            # Webhook URLs
    notify_on_failure: List[str]
    notify_on_missed: List[str]
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_duration: float = 0.0
    
    # SLA
    max_duration: Optional[float]           # Alert if task takes longer
    expected_duration: Optional[float]      # Expected duration for anomaly detection


class CronSchedule:
    """Cron expression parser and next-run calculator."""
    expression: str                         # e.g., "0 9 * * MON"
    timezone: str                           # e.g., "America/New_York"
    business_hours_only: bool = False
    business_hours: Optional[Tuple[int, int]]  # e.g., (9, 17)
    exclude_weekends: bool = False
    exclude_holidays: bool = False
    holiday_calendar: Optional[str]         # Country code for holiday calendar
    
    def next_occurrence(self, after: datetime) -> datetime:
        """Calculate next scheduled occurrence."""
    
    def should_run_now(self, now: datetime) -> bool:
        """Check if the schedule triggers now."""
    
    def get_upcoming(self, count: int = 10) -> List[datetime]:
        """Get next N scheduled occurrences."""
```

#### 6.2.2 `browser_agent/scheduling/scheduler.py`

```python
class TaskScheduler:
    """Cron-like scheduler for recurring browser automation tasks."""
    
    def __init__(
        self,
        agent_factory: Callable,
        audit_log: AuditLog,
        store: ScheduleStore,
        health_monitor: HealthMonitor,
    ): ...
    
    async def register(self, task: RecurringTask) -> str:
        """Register a new recurring task."""
    
    async def unregister(self, task_id: str) -> bool:
        """Unregister a recurring task."""
    
    async def update(self, task_id: str, updates: Dict) -> RecurringTask:
        """Update task schedule or parameters."""
    
    async def trigger(self, task_id: str) -> TaskRun:
        """Manually trigger a task run (outside schedule)."""
    
    async def start(self):
        """Start the scheduler loop."""
    
    async def stop(self):
        """Gracefully stop scheduler."""
    
    async def list_tasks(
        self,
        tenant_id: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[RecurringTask]:
        """List registered tasks."""
    
    async def get_run_history(
        self,
        task_id: str,
        limit: int = 50,
    ) -> List[TaskRun]:
        """Get execution history for a task."""


class TaskRun:
    """Record of a single task execution."""
    run_id: str
    task_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str                             # "running", "completed", "failed", "timeout", "missed"
    result: Optional[Dict]
    checkpoint_used: Optional[str]          # Checkpoint ID used for resume
    error: Optional[str]
    duration: Optional[float]
```

#### 6.2.3 `browser_agent/scheduling/health_monitor.py`

```python
class ScheduleHealthMonitor:
    """Monitor scheduled task health and alert on issues."""
    
    def __init__(self, notifiers: List[Notifier]): ...
    
    async def check_health(self) -> ScheduleHealthReport:
        """Check all scheduled tasks health."""
    
    async def record_run(self, run: TaskRun):
        """Record a task run result."""
    
    async def detect_anomalies(self) -> List[ScheduleAnomaly]:
        """Detect anomalies in scheduled task execution."""
        # - Task not running on schedule (missed)
        # - Task taking much longer than expected
        # - Success rate dropping below threshold
        # - Checkpoint used repeatedly (stuck)
    
    async def check_sla(self, task: RecurringTask, run: TaskRun) -> Optional[SLAViolation]:
        """Check if a task run violated SLA."""


@dataclass
class ScheduleHealthReport:
    total_tasks: int
    healthy_tasks: int
    degraded_tasks: int
    unhealthy_tasks: int
    missed_runs_24h: int
    avg_success_rate: float
    anomalies: List[ScheduleAnomaly]


@dataclass
class ScheduleAnomaly:
    task_id: str
    anomaly_type: str                       # "missed_run", "duration_spike", "success_rate_drop"
    severity: str                           # "warning", "critical"
    details: str
    detected_at: datetime
```

#### 6.2.4 `browser_agent/scheduling/calendar.py`

```python
class BusinessCalendar:
    """Business hours and holiday calendar support."""
    
    def __init__(self, timezone: str, holidays_country: Optional[str] = None): ...
    
    def is_business_hours(self, dt: datetime) -> bool:
        """Check if datetime is within business hours."""
    
    def is_holiday(self, dt: datetime) -> bool:
        """Check if datetime is a holiday."""
    
    def is_weekend(self, dt: datetime) -> bool:
        """Check if datetime is a weekend."""
    
    def next_business_time(self, after: datetime) -> datetime:
        """Get next valid business time."""
    
    def add_holidays(self, dates: List[datetime]):
        """Add custom holidays."""
```

### 6.3 API Endpoints

```
POST   /schedules                          # Create recurring task
GET    /schedules                          # List recurring tasks
GET    /schedules/{task_id}                # Get task details
PUT    /schedules/{task_id}                # Update task
DELETE /schedules/{task_id}                # Delete task
POST   /schedules/{task_id}/trigger        # Manually trigger
GET    /schedules/{task_id}/runs           # Get run history
GET    /schedules/{task_id}/runs/{run_id}  # Get specific run
GET    /schedules/health                   # Get health report
GET    /schedules/upcoming                 # Get upcoming scheduled runs
```

### 6.4 Configuration

```yaml
scheduling:
  enabled: true
  store_type: sqlite
  store_path: .scheduling/schedules.db
  check_interval: 60                       # Check for due tasks every 60 seconds
  max_concurrent_runs: 5                   # Max simultaneous scheduled task runs
  default_timezone: "UTC"
  health_check_interval: 300              # Check health every 5 minutes
  
  notifications:
    on_success: false                      # Notify on successful run
    on_failure: true                       # Notify on failed run
    on_missed: true                        # Notify on missed schedule
    on_sla_violation: true                 # Notify on SLA violation
    channels:
      - type: webhook
        url: ${SCHEDULE_WEBHOOK_URL}
```

### 6.5 Tests

```
tests/test_scheduling/
├── test_cron_schedule.py          # 12 tests — parsing, next occurrence, business hours
├── test_recurring_task.py         # 10 tests — task creation, validation
├── test_scheduler.py              # 15 tests — register, trigger, run, resume
├── test_health_monitor.py         # 10 tests — anomaly detection, SLA, health report
├── test_business_calendar.py      # 8 tests — business hours, holidays, weekends
└── test_scheduling_api.py         # 12 tests — API endpoints
```

### 6.6 Tasks

| # | Task | Est. | Status |
|---|------|------|--------|
| 9.1 | Implement `CronSchedule` — parsing, next occurrence, business hours | 1d | [x] |
| 9.2 | Implement `RecurringTask` dataclass and validation | 0.5d | [x] |
| 9.3 | Implement `BusinessCalendar` | 0.5d | [x] |
| 9.4 | Implement `TaskScheduler` — register, trigger, start/stop loop | 2d | [x] |
| 9.5 | Implement checkpoint-based resume in scheduler | 1d | [x] |
| 9.6 | Implement `ScheduleHealthMonitor` | 1d | [x] |
| 9.7 | Implement schedule notifications | 0.5d | [x] |
| 9.8 | Add scheduling API endpoints | 1d | [x] |
| 9.9 | Write config schema | 0.5d | [x] |
| 9.10 | Write all tests | 2d | [x] |

**Total: ~10 days**

---

## 7. Phase 10: Data Loss Prevention (DLP)

**Duration:** 1.5 weeks (Week 7–9)
**Priority:** 🟡 High
**Depends on:** Phase 7 (data classifier from audit trail)

### 7.1 Objectives

- Detect PII, PHI, and financial data in agent inputs and outputs
- Prevent sensitive data from being sent to external LLM APIs
- Redact or mask sensitive data before it leaves the system
- Log all DLP events for compliance

### 7.2 Components

#### 7.2.1 `browser_agent/security/pii_detector.py`

```python
class PIIDetector:
    """Detect personally identifiable information in text."""
    
    def __init__(self, custom_patterns: Optional[Dict[str, str]] = None): ...
    
    def detect(self, text: str) -> List[PIIMatch]:
        """Scan text for PII patterns."""
    
    def detect_in_dict(self, data: Dict) -> Dict[str, List[PIIMatch]]:
        """Scan all values in a dictionary."""
    
    def has_pii(self, text: str) -> bool:
        """Quick check if text contains PII."""
    
    def get_pii_types(self, text: str) -> List[PIIType]:
        """Get list of PII types found in text."""


class PIIType(Enum):
    SSN = "ssn"                             # Social Security Number
    CREDIT_CARD = "credit_card"             # Credit card number
    PHONE = "phone"                         # Phone number
    EMAIL = "email"                         # Email address
    DATE_OF_BIRTH = "date_of_birth"         # Date of birth
    ADDRESS = "address"                     # Physical address
    PASSPORT = "passport"                   # Passport number
    DRIVER_LICENSE = "driver_license"       # Driver's license
    BANK_ACCOUNT = "bank_account"           # Bank account number
    IP_ADDRESS = "ip_address"               # IP address (PII under GDPR)
    MEDICAL_RECORD = "medical_record"       # Medical record number
    NAME = "name"                           # Person's full name
    API_KEY = "api_key"                     # API key/secret
    PASSWORD = "password"                   # Password in text
    CUSTOM = "custom"                       # Custom pattern


@dataclass
class PIIMatch:
    pii_type: PIIType
    value: str                              # The matched text
    start: int                              # Start position
    end: int                                # End position
    confidence: float                       # Detection confidence 0-1
    masked: str                             # Masked version


# Built-in patterns (regex)
BUILTIN_PATTERNS = {
    PIIType.SSN: [
        r'\b\d{3}-\d{2}-\d{4}\b',                        # XXX-XX-XXXX
        r'\b\d{3}\s\d{2}\s\d{4}\b',                      # XXX XX XXXX
    ],
    PIIType.CREDIT_CARD: [
        r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # 16 digits
        r'\b\d{4}[\s-]?\d{6}[\s-]?\d{5}\b',              # 15 digits (Amex)
    ],
    PIIType.EMAIL: [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    ],
    PIIType.PHONE: [
        r'\b\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b',
        r'\b\+\d{1,3}\s\d{2,3}\s\d{3}\s\d{4}\b',
    ],
    PIIType.DATE_OF_BIRTH: [
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
    ],
    PIIType.IP_ADDRESS: [
        r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
    ],
    PIIType.API_KEY: [
        r'(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*["\']?[\w\-]{16,}["\']?',
        r'\bsk-[a-zA-Z0-9]{32,}\b',                       # OpenAI-style keys
        r'\bAKIA[0-9A-Z]{16}\b',                          # AWS access keys
    ],
    PIIType.BANK_ACCOUNT: [
        r'\b\d{8,17}\b',                                  # Generic bank account
    ],
}
```

#### 7.2.2 `browser_agent/security/redaction.py`

```python
class RedactionStrategy(Enum):
    MASK = "mask"            # Replace with asterisks: "123-45-6789" → "***-**-6789"
    REPLACE = "replace"      # Replace with type label: "123-45-6789" → "[SSN]"
    HASH = "hash"            # Replace with hash: "123-45-6789" → "[SSN:abc123]"
    REMOVE = "remove"        # Remove entirely
    PARTIAL = "partial"      # Show first/last chars: "John Smith" → "J*** S***"


class DataRedactor:
    """Redact PII from text and data structures."""
    
    def __init__(
        self,
        strategy: RedactionStrategy = RedactionStrategy.MASK,
        pii_types: Optional[List[PIIType]] = None,
        preserve_types: Optional[List[PIIType]] = None,
    ): ...
    
    def redact_text(self, text: str, matches: List[PIIMatch]) -> RedactedText:
        """Redact PII from text."""
    
    def redact_dict(self, data: Dict, matches: Dict[str, List[PIIMatch]]) -> Dict:
        """Redact PII from dictionary values."""
    
    def redact_screenshot(self, image: bytes, regions: List[PIIRegion]) -> bytes:
        """Blur/redact PII regions in screenshots (before sending to LLM)."""
    
    def create_token_map(self, text: str, matches: List[PIIMatch]) -> TokenMap:
        """Create reversible token mapping (for later de-tokenization)."""


@dataclass
class RedactedText:
    original_hash: str          # Hash of original text
    redacted_text: str          # Text with PII redacted
    redaction_count: int        # Number of redactions
    redacted_types: List[PIIType]
    token_map: Optional[TokenMap]  # For reversing redactions


class TokenMap:
    """Reversible mapping of redacted values to tokens."""
    _mapping: Dict[str, str]   # token → original value
    
    def detokenize(self, text: str) -> str:
        """Replace tokens back with original values."""
    
    def get_original(self, token: str) -> Optional[str]:
        """Get original value for a token."""
    
    def clear(self):
        """Securely clear the mapping."""
```

#### 7.2.3 `browser_agent/security/dlp.py`

```python
class DLPPolicy:
    """DLP policy configuration."""
    action: DLPAction                        # What to do when PII detected
    pii_types: List[PIIType]                 # Which PII types to detect
    redaction_strategy: RedactionStrategy
    confidence_threshold: float = 0.7        # Min confidence to trigger
    scan_prompts: bool = True                # Scan LLM prompts before sending
    scan_responses: bool = True              # Scan LLM responses
    scan_extractions: bool = True            # Scan extracted data
    scan_screenshots: bool = False           # OCR + scan screenshots (expensive)
    block_on_detection: bool = False         # Block action entirely
    alert_on_detection: bool = True          # Send alert
    log_on_detection: bool = True            # Log to audit trail


class DLPAction(Enum):
    REDACT = "redact"          # Redact and continue
    BLOCK = "block"            # Block the action
    ALERT = "alert"            # Alert but continue
    LOG = "log"                # Log only


class DLPEngine:
    """Data Loss Prevention engine."""
    
    def __init__(
        self,
        detector: PIIDetector,
        redactor: DataRedactor,
        policy: DLPPolicy,
        audit_log: Optional[AuditLog] = None,
    ): ...
    
    async def scan_text(self, text: str, context: str) -> DLPResult:
        """Scan text for PII and apply policy."""
    
    async def scan_dict(self, data: Dict, context: str) -> DLPResult:
        """Scan dictionary for PII."""
    
    async def scan_prompt(self, prompt: str) -> DLPResult:
        """Scan LLM prompt before sending."""
    
    async def scan_response(self, response: str) -> DLPResult:
        """Scan LLM response."""
    
    async def scan_extraction(self, data: Any) -> DLPResult:
        """Scan extracted data before returning to caller."""
    
    async def scan_screenshot(self, image: bytes) -> DLPScreenshotResult:
        """OCR + scan screenshot (if enabled)."""


@dataclass
class DLPResult:
    has_violations: bool
    action_taken: DLPAction
    violations: List[DLPViolation]
    redacted_content: Optional[Any]
    original_content_hash: str
    scan_duration_ms: float


@dataclass
class DLPViolation:
    pii_type: PIIType
    field_name: Optional[str]
    confidence: float
    value_hash: str               # Hash of the original value (not the value itself)
    action_taken: DLPAction
    location: str                 # Where found: "prompt", "response", "extraction", "screenshot"
```

### 7.3 Integration Points

```python
# In browser_agent/llm/client.py — DLP scanning of prompts

class LLMClient:
    def __init__(self, ..., dlp_engine: Optional[DLPEngine] = None):
        self._dlp = dlp_engine
    
    async def chat(self, messages, ...):
        # Scan prompt
        if self._dlp:
            prompt_text = " ".join(m.content for m in messages)
            dlp_result = await self._dlp.scan_prompt(prompt_text)
            if dlp_result.action_taken == DLPAction.BLOCK:
                raise DLPPolicyViolation(dlp_result.violations)
            if dlp_result.redacted_content:
                # Use redacted prompt instead
                messages = self._apply_redaction(messages, dlp_result.redacted_content)
        
        response = await self._chat_api_call(messages, ...)
        
        # Scan response
        if self._dlp:
            resp_result = await self._dlp.scan_response(response.content)
            if resp_result.redacted_content:
                response.content = resp_result.redacted_content
        
        return response
```

```python
# In browser_agent/skills/data_extraction.py — DLP scanning of extracted data

class DataExtractionSkill:
    def __init__(self, ..., dlp_engine: Optional[DLPEngine] = None):
        self._dlp = dlp_engine
    
    async def execute(self, skill_input):
        result = await self._extract(skill_input)
        
        if self._dlp:
            dlp_result = await self._dlp.scan_extraction(result.data)
            if dlp_result.action_taken == DLPAction.BLOCK:
                raise DLPPolicyViolation(dlp_result.violations)
            if dlp_result.redacted_content:
                result.data = dlp_result.redacted_content
        
        return result
```

### 7.4 API Endpoints

```
POST   /dlp/scan                       # Scan text/data for PII
GET    /dlp/policy                     # Get current DLP policy
PUT    /dlp/policy                     # Update DLP policy
GET    /dlp/violations                 # Get DLP violation history
POST   /dlp/test                       # Test DLP against sample text
```

### 7.5 Configuration

```yaml
security:
  dlp:
    enabled: true
    action: redact                        # redact | block | alert | log
    redaction_strategy: mask              # mask | replace | hash | remove | partial
    confidence_threshold: 0.7
    
    scan:
      prompts: true                       # Scan LLM prompts
      responses: true                     # Scan LLM responses
      extractions: true                   # Scan extracted data
      screenshots: false                  # OCR screenshots (expensive)
    
    pii_types:                            # Which types to detect (all if not specified)
      - ssn
      - credit_card
      - email
      - phone
      - api_key
      - password
      - medical_record
    
    custom_patterns:                      # Custom regex patterns
      employee_id: "EMP-\d{6}"
      project_code: "PRJ-[A-Z]{3}-\d{3}"
    
    alerting:
      enabled: true
      webhook_url: ${DLP_ALERT_WEBHOOK}
      min_severity: warning
```

### 7.6 Tests

```
tests/test_security/
├── test_pii_detector.py           # 18 tests — each PII type, confidence, custom patterns
├── test_redaction.py              # 15 tests — each strategy, dict redaction, token map
├── test_dlp_engine.py             # 15 tests — scan, block, redact, alert flows
├── test_dlp_integration.py        # 10 tests — integration with LLM client and skills
└── test_dlp_api.py                # 10 tests — API endpoints
```

### 7.7 Tasks

| # | Task | Est. | Status |
|---|------|------|--------|
| 10.1 | Implement `PIIDetector` with all built-in patterns | 1.5d | [x] |
| 10.2 | Implement custom pattern support | 0.5d | [x] |
| 10.3 | Implement `DataRedactor` with all strategies | 1.5d | [x] |
| 10.4 | Implement `TokenMap` for reversible redaction | 0.5d | [x] |
| 10.5 | Implement `DLPEngine` — scan, policy enforcement | 1.5d | [x] |
| 10.6 | Integrate DLP into `LLMClient` (prompt/response scanning) | 1d | [x] |
| 10.7 | Integrate DLP into `DataExtractionSkill` | 0.5d | [x] |
| 10.8 | Integrate DLP into `BrowserAgent` (screenshot scanning) | 0.5d | [x] |
| 10.9 | Add DLP API endpoints | 0.5d | [x] |
| 10.10 | Write config schema | 0.5d | [x] |
| 10.11 | Write all tests | 2d | [x] |

**Total: ~10 days**

---

## 8. Phase 11: Multi-Tenant Task Orchestrator

**Duration:** 2.5 weeks (Week 9–11)
**Priority:** 🟢 Strategic
**Depends on:** Phase 6 (per-tenant credentials), Phase 7 (per-tenant audit), Phase 8 (per-tenant policies)

### 8.1 Objectives

- Run browser automation for multiple isolated tenants on shared infrastructure
- Fair scheduling across tenants with configurable resource quotas
- Per-tenant billing/metering hooks
- Tenant onboarding, management, and isolation enforcement

### 8.2 Components

#### 8.2.1 `browser_agent/orchestration/tenant_manager.py`

```python
class Tenant:
    tenant_id: str
    name: str
    plan: TenantPlan
    status: TenantStatus
    
    # Resource limits
    max_concurrent_tasks: int = 3
    max_daily_tasks: int = 100
    max_monthly_tasks: int = 2000
    max_browser_workers: int = 2
    max_task_timeout: float = 600.0       # Max task duration
    max_steps_per_task: int = 50
    
    # Feature flags
    features: Dict[str, bool]             # "dlp", "scheduling", "recording", etc.
    
    # Isolation
    credential_scope: str                 # Vault namespace / path prefix
    audit_scope: str                      # Audit log partition key
    data_scope: str                       # Data storage isolation
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    owner_email: str
    admin_emails: List[str]
    metadata: Dict[str, Any]


class TenantPlan(Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class TenantStatus(Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    CLOSED = "closed"


class TenantManager:
    """Manage multi-tenant isolation and lifecycle."""
    
    def __init__(self, store: TenantStore): ...
    
    async def create_tenant(self, name: str, plan: TenantPlan, owner_email: str, **kwargs) -> Tenant:
        """Create a new tenant with default configuration."""
    
    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant details."""
    
    async def update_tenant(self, tenant_id: str, updates: Dict) -> Tenant:
        """Update tenant configuration."""
    
    async def suspend_tenant(self, tenant_id: str, reason: str) -> bool:
        """Suspend tenant (cancel all running tasks)."""
    
    async def delete_tenant(self, tenant_id: str) -> bool:
        """Soft-delete tenant and all associated data."""
    
    async def validate_access(self, tenant_id: str, api_key: str) -> bool:
        """Validate API key belongs to tenant."""
    
    async def check_quota(self, tenant_id: str, resource: str) -> QuotaCheck:
        """Check if tenant has quota remaining for a resource."""
```

#### 8.2.2 `browser_agent/orchestration/resource_pool.py`

```python
class BrowserWorker:
    """A browser instance available for task execution."""
    worker_id: str
    browser_type: str
    status: WorkerStatus                    # idle, busy, initializing, error
    current_task_id: Optional[str]
    current_tenant_id: Optional[str]
    started_at: datetime
    last_activity: datetime
    total_tasks_completed: int
    health: WorkerHealth


class WorkerStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    INITIALIZING = "initializing"
    ERROR = "error"
    DRAINING = "draining"                  # Finishing current task, then shutting down


class WorkerHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ResourcePool:
    """Pool of browser workers for multi-tenant task execution."""
    
    def __init__(self, config: ResourcePoolConfig): ...
    
    async def acquire(self, tenant_id: str, timeout: float = 30.0) -> BrowserWorker:
        """
        Acquire a browser worker for a tenant.
        - Respects tenant max_workers limit
        - Creates new worker if pool has capacity
        - Waits if no workers available
        """
    
    async def release(self, worker: BrowserWorker):
        """Release worker back to pool."""
    
    async def drain(self, worker_id: str):
        """Gracefully drain a worker (finish current task, then remove)."""
    
    async def health_check(self) -> PoolHealthReport:
        """Check health of all workers."""
    
    async def scale(self, target_size: int):
        """Scale pool to target size."""
    
    @property
    def idle_count(self) -> int:
        """Number of idle workers."""
    
    @property
    def total_count(self) -> int:
        """Total number of workers."""


class ResourcePoolConfig:
    min_workers: int = 2                   # Minimum idle workers
    max_workers: int = 20                  # Maximum total workers
    idle_timeout: float = 300.0            # Shutdown idle workers after N seconds
    health_check_interval: float = 60.0
    browser_type: str = "chromium"
    headless: bool = True
```

#### 8.2.3 `browser_agent/orchestration/scheduler_fair.py`

```python
class FairScheduler:
    """Fair-share scheduler across tenants."""
    
    def __init__(
        self,
        tenant_manager: TenantManager,
        resource_pool: ResourcePool,
        quota_manager: QuotaManager,
    ): ...
    
    async def submit(self, task: TenantTask) -> str:
        """Submit task to tenant's queue."""
    
    async def cancel(self, task_id: str, tenant_id: str) -> bool:
        """Cancel a queued or running task."""
    
    async def get_position(self, task_id: str) -> int:
        """Get task position in queue."""
    
    async def start(self):
        """Start scheduler loop."""
    
    async def stop(self):
        """Gracefully stop scheduler."""
    
    def get_queue_stats(self, tenant_id: str) -> TenantQueueStats:
        """Get queue statistics for a tenant."""


class TenantTask:
    """Task scoped to a tenant."""
    task_id: str
    tenant_id: str
    goal: str
    start_url: Optional[str]
    priority: int = 0                      # Within-tenant priority
    submitted_at: datetime
    submitted_by: str
    credential_aliases: Optional[Dict[str, str]]
    config_overrides: Dict[str, Any]
    
    # Scheduling
    scheduled_at: Optional[datetime]       # When to start (for scheduled tasks)
    deadline: Optional[datetime]           # Must complete by this time


@dataclass
class TenantQueueStats:
    tenant_id: str
    pending_tasks: int
    running_tasks: int
    completed_today: int
    quota_remaining: Dict[str, int]
    avg_wait_time: float
    avg_execution_time: float
```

#### 8.2.4 `browser_agent/orchestration/quotas.py`

```python
class QuotaManager:
    """Track and enforce resource quotas per tenant."""
    
    def __init__(self, store: QuotaStore): ...
    
    async def check(self, tenant_id: str, resource: str, amount: int = 1) -> QuotaCheck:
        """Check if tenant can use `amount` of `resource`."""
    
    async def consume(self, tenant_id: str, resource: str, amount: int = 1) -> bool:
        """Consume quota. Returns False if quota exceeded."""
    
    async def reset(self, tenant_id: str, resource: str):
        """Reset quota for a resource (e.g., daily reset)."""
    
    async def get_usage(self, tenant_id: str) -> Dict[str, UsageRecord]:
        """Get current usage for all resources."""


class QuotaCheck:
    allowed: bool
    resource: str
    limit: int
    used: int
    remaining: int
    reset_at: Optional[datetime]


@dataclass
class UsageRecord:
    resource: str
    used: int
    limit: int
    period: str              # "daily", "monthly", "total"
    reset_at: datetime
```

#### 8.2.5 `browser_agent/orchestration/metering.py`

```python
class MeteringEngine:
    """Usage metering for billing integration."""
    
    def __init__(self, store: MeteringStore): ...
    
    async def record_task(self, tenant_id: str, run: TaskRun):
        """Record task execution for metering."""
    
    async def record_tokens(self, tenant_id: str, model: str, prompt_tokens: int, completion_tokens: int):
        """Record LLM token usage."""
    
    async def record_actions(self, tenant_id: str, action_count: int):
        """Record action count."""
    
    async def get_billable_events(
        self,
        tenant_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[BillableEvent]:
        """Get billable events for a period."""
    
    async def generate_invoice_data(
        self,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> InvoiceData:
        """Generate invoice data for a billing period."""


@dataclass
class BillableEvent:
    event_id: str
    tenant_id: str
    event_type: str                     # "task", "tokens", "actions"
    quantity: int
    unit: str                           # "task", "1k_tokens", "100_actions"
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass
class InvoiceData:
    tenant_id: str
    period_start: datetime
    period_end: datetime
    line_items: List[InvoiceLineItem]
    total_tasks: int
    total_tokens: int
    total_actions: int
    total_cost_estimate: float


class InvoiceLineItem:
    description: str
    quantity: int
    unit_price: float
    total: float
```

### 8.3 API Middleware

```python
# browser_agent/api/middleware/tenant_resolver.py

class TenantResolverMiddleware:
    """
    Extract tenant_id from API request.
    
    Resolution order:
    1. X-Tenant-ID header + API key validation
    2. JWT token with tenant claim
    3. API key → tenant mapping
    """
    
    async def __call__(self, request, call_next):
        tenant_id = await self._resolve_tenant(request)
        if not tenant_id:
            return JSONResponse(status_code=401, content={"error": "Invalid tenant credentials"})
        
        # Attach tenant to request state
        request.state.tenant_id = tenant_id
        request.state.tenant = await self.tenant_manager.get_tenant(tenant_id)
        
        # Check tenant status
        if request.state.tenant.status == TenantStatus.SUSPENDED:
            return JSONResponse(status_code=403, content={"error": "Tenant suspended"})
        
        response = await call_next(request)
        return response
```

### 8.4 API Endpoints

```
# Tenant management (admin only)
POST   /tenants                           # Create tenant
GET    /tenants                           # List tenants
GET    /tenants/{tenant_id}               # Get tenant details
PUT    /tenants/{tenant_id}               # Update tenant
DELETE /tenants/{tenant_id}               # Delete tenant
POST   /tenants/{tenant_id}/suspend       # Suspend tenant
POST   /tenants/{tenant_id}/activate      # Activate tenant

# Quota & usage (tenant-scoped)
GET    /usage                             # Get current usage
GET    /usage/quotas                      # Get quota limits
GET    /usage/history                     # Get usage history
GET    /billing/invoice                   # Get current invoice data

# Task submission (tenant-scoped — uses existing /tasks with tenant context)
POST   /tasks                             # Submit task (auto-scoped to tenant)
```

### 8.5 Configuration

```yaml
orchestration:
  multi_tenant: true
  
  resource_pool:
    min_workers: 2
    max_workers: 20
    idle_timeout: 300
    health_check_interval: 60
    browser_type: chromium
    headless: true
  
  scheduler:
    type: fair                            # fair | fifo | priority
    check_interval: 5                     # Check for new tasks every 5 seconds
    default_task_timeout: 300
    max_task_timeout: 3600
  
  defaults:
    plan: starter
    max_concurrent_tasks: 3
    max_daily_tasks: 100
    max_monthly_tasks: 2000
    max_browser_workers: 2
  
  metering:
    enabled: true
    store_type: sqlite
    store_path: .orchestration/metering.db
    billing_period: monthly               # daily | weekly | monthly
    pricing:
      task: 0.10                          # $0.10 per task
      tokens_per_1k: 0.002               # $0.002 per 1K tokens
      actions_per_100: 0.05              # $0.05 per 100 actions
```

### 8.6 Tests

```
tests/test_orchestration/
├── test_tenant_manager.py         # 15 tests — CRUD, suspend, delete, isolation
├── test_resource_pool.py          # 15 tests — acquire, release, drain, health, scale
├── test_fair_scheduler.py         # 15 tests — submit, cancel, fair-share, priority
├── test_quotas.py                 # 12 tests — check, consume, reset, enforcement
├── test_metering.py               # 10 tests — record, billable events, invoice
├── test_tenant_middleware.py      # 8 tests — resolution, auth, status check
├── test_isolation.py              # 10 tests — cross-tenant isolation verification
└── test_orchestration_api.py      # 15 tests — API endpoints
```

### 8.7 Tasks

| # | Task | Est. | Status |
|---|------|------|--------|
| 11.1 | Implement `Tenant`, `TenantManager` | 1.5d | [x] |
| 11.2 | Implement `ResourcePool` — acquire, release, drain, scale | 2d | [x] |
| 11.3 | Implement `FairScheduler` — submit, cancel, fair-share | 2d | [x] |
| 11.4 | Implement `QuotaManager` — check, consume, reset | 1d | [x] |
| 11.5 | Implement `MeteringEngine` — record, invoice | 1.5d | [x] |
| 11.6 | Implement `TenantResolverMiddleware` | 1d | [x] |
| 11.7 | Integrate tenant scoping into existing `TaskManager` | 1d | [x] |
| 11.8 | Implement tenant isolation verification | 1d | [x] |
| 11.9 | Add orchestration API endpoints | 1d | [x] |
| 11.10 | Write config schema | 0.5d | [x] |
| 11.11 | Write all tests | 2.5d | [x] |

**Total: ~15 days**

---

## 9. Phase 12: Workflow Recording & Replay

**Duration:** 2.5 weeks (Week 11–14)
**Priority:** 🟢 Strategic
**Depends on:** Phase 6 (credentials in recordings), Phase 10 (DLP on recorded data)

### 9.1 Objectives

- Record a user performing a browser workflow step by step
- Parameterize the recording so it can be replayed with different data
- Replay deterministically when the page hasn't changed
- Fall back to vision-guided (UI-TARS) when the page has changed
- Version recordings and track changes

### 9.2 Components

#### 9.2.1 `browser_agent/recording/recorder.py`

```python
class RecordedAction:
    """A single recorded action."""
    action_id: str
    step_index: int
    
    # What happened
    action_type: str                        # "click", "type_text", "navigate", etc.
    target_url: str                         # URL at time of action
    parameters: Dict[str, Any]              # Action parameters
    
    # Visual context
    screenshot_before: Optional[bytes]      # Screenshot before action
    screenshot_after: Optional[bytes]       # Screenshot after action
    screenshot_before_hash: Optional[str]
    screenshot_after_hash: Optional[str]
    
    # Element context
    target_selector: Optional[str]          # CSS selector (if available)
    target_coordinates: Optional[Tuple[int, int]]
    target_description: Optional[str]       # Visual description
    target_text: Optional[str]              # Text content of element
    target_element_type: Optional[str]      # "button", "input", "link", etc.
    
    # Page context
    page_title: Optional[str]
    page_url: Optional[str]
    page_state_hash: Optional[str]          # Hash of page DOM for change detection
    
    # Result
    success: bool
    result_data: Optional[Dict]
    error: Optional[str]
    
    # Parameterization
    is_parameterized: bool = False
    parameter_name: Optional[str]           # e.g., "vendor_name"
    parameter_type: Optional[str]           # "text", "url", "option"
    original_value: Optional[Any]           # Original value before parameterization
    
    timestamp: float


class Recording:
    """A recorded workflow."""
    recording_id: str
    name: str
    description: str
    tenant_id: str
    created_by: str
    
    # Recording
    actions: List[RecordedAction]
    total_steps: int
    start_url: str
    end_url: Optional[str]
    
    # Parameters
    parameters: List[RecordingParameter]     # Parameterized values
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    version: int = 1
    tags: List[str] = []
    
    # Execution stats
    run_count: int = 0
    success_count: int = 0
    avg_duration: float = 0.0
    last_run: Optional[datetime]
    
    # Versioning
    parent_version: Optional[int] = None
    change_description: Optional[str] = None


class RecordingParameter:
    """A parameterized value in a recording."""
    name: str                               # e.g., "vendor_name"
    display_name: str                       # "Vendor Name"
    parameter_type: str                     # "text", "url", "select", "date", "email"
    default_value: Any                      # Default value from original recording
    required: bool = True
    description: Optional[str]
    validation_pattern: Optional[str]       # Regex for validation
    options: Optional[List[str]]            # For select type
    field_index: Optional[int]              # Which action step uses this parameter


class WorkflowRecorder:
    """Record browser workflows step by step."""
    
    def __init__(
        self,
        browser: BrowserController,
        vision_client: Optional[VisionClient] = None,
        screenshot_interval: int = 1,       # Screenshot every N actions
    ): ...
    
    async def start_recording(
        self,
        name: str,
        start_url: str,
        description: Optional[str] = None,
    ) -> Recording:
        """Start recording a new workflow."""
    
    async def record_action(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        result: ActionResult,
    ) -> RecordedAction:
        """
        Record a single action.
        Called by the agent after each action execution.
        Captures screenshots, element context, and result.
        """
    
    async def stop_recording(self) -> Recording:
        """Stop recording and return the completed recording."""
    
    async def pause_recording(self):
        """Pause recording (skip actions)."""
    
    async def resume_recording(self):
        """Resume recording."""
```

#### 9.2.2 `browser_agent/recording/parameterizer.py`

```python
class RecordingParameterizer:
    """Convert recorded values into reusable parameters."""
    
    async def auto_detect_parameters(self, recording: Recording) -> List[RecordingParameter]:
        """
        Automatically detect parameterizable values.
        - Typed text → text parameters
        - URLs → url parameters  
        - Dates → date parameters
        - Selected options → select parameters
        - Values that look like names/emails → text/email parameters
        """
    
    async def parameterize_action(
        self,
        recording: Recording,
        action_index: int,
        field: str,                          # "parameters.text", "parameters.url", etc.
        parameter_name: str,
        parameter_type: str = "text",
    ) -> Recording:
        """Mark a specific field in an action as a parameter."""
    
    async def remove_parameterization(
        self,
        recording: Recording,
        action_index: int,
        field: str,
    ) -> Recording:
        """Remove parameterization from a field."""
    
    async def validate_parameters(
        self,
        parameters: Dict[str, Any],
        recording: Recording,
    ) -> ValidationResult:
        """Validate provided parameters against recording requirements."""
```

#### 9.2.3 `browser_agent/recording/player.py`

```python
class ReplayMode(Enum):
    STRICT = "strict"               # Exact selector/coordinately replay, fail if page changed
    ADAPTIVE = "adaptive"           # Try exact, fall back to vision if mismatch
    VISION_ONLY = "vision_only"     # Use UI-TARS for every step (slow but resilient)


class WorkflowPlayer:
    """Replay recorded workflows."""
    
    def __init__(
        self,
        browser: BrowserController,
        vision_client: Optional[VisionClient] = None,
        agent: Optional[BrowserAgent] = None,
        mode: ReplayMode = ReplayMode.ADAPTIVE,
    ): ...
    
    async def play(
        self,
        recording: Recording,
        parameters: Optional[Dict[str, Any]] = None,
        on_step: Optional[Callable] = None,  # Callback after each step
    ) -> ReplayResult:
        """
        Replay a recorded workflow.
        
        Args:
            recording: The recording to replay
            parameters: Parameter values (for parameterized recordings)
            on_step: Callback(ReplayStepResult) after each step
        
        Returns:
            ReplayResult with step-by-step outcomes
        """
    
    async def play_step(
        self,
        action: RecordedAction,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ReplayStepResult:
        """
        Replay a single step.
        
        Strategy (adaptive mode):
        1. Check if page matches recorded state (DOM hash, screenshot similarity)
        2. If match: replay exact action (selector/coordinates)
        3. If mismatch: use vision model to find element
        4. Execute and verify
        """
    
    async def dry_run(
        self,
        recording: Recording,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> DryRunResult:
        """
        Simulate replay without executing.
        Checks page state matches, element availability, etc.
        """


@dataclass
class ReplayResult:
    recording_id: str
    success: bool
    total_steps: int
    completed_steps: int
    failed_step: Optional[int]
    step_results: List[ReplayStepResult]
    parameters_used: Dict[str, Any]
    execution_time: float
    adaptive_fallbacks: int              # How many steps needed vision fallback
    screenshots: List[bytes]


@dataclass
class ReplayStepResult:
    step_index: int
    action_type: str
    success: bool
    strategy_used: str                   # "exact" or "vision_fallback"
    page_matched: bool                   # Did page match recorded state?
    error: Optional[str]
    execution_time: float
    screenshot: Optional[bytes]
```

#### 9.2.4 `browser_agent/recording/adaptive_replay.py`

```python
class AdaptiveReplay:
    """Self-healing replay that adapts to page changes."""
    
    def __init__(self, vision_client: VisionClient): ...
    
    async def match_page_state(
        self,
        current_screenshot: bytes,
        recorded_screenshot: bytes,
        threshold: float = 0.85,
    ) -> PageMatchResult:
        """
        Compare current page to recorded state.
        Uses perceptual hashing + structural comparison.
        """
    
    async def find_element(
        self,
        current_screenshot: bytes,
        recorded_action: RecordedAction,
    ) -> ElementMatch:
        """
        Find the equivalent element on a changed page.
        Uses:
        1. Selector match (fast)
        2. Text content match (medium)
        3. Visual description match via UI-TARS (slow, accurate)
        4. Position heuristic (last resort)
        """
    
    async def verify_action_result(
        self,
        before_screenshot: bytes,
        after_screenshot: bytes,
        expected_change: str,
    ) -> bool:
        """Verify the action had the expected effect."""


@dataclass
class PageMatchResult:
    matches: bool
    similarity: float
    changed_regions: List[Tuple[int, int, int, int]]
    structural_changes: List[str]        # "element_added", "element_removed", "layout_changed"


@dataclass
class ElementMatch:
    found: bool
    strategy: str                        # "selector", "text", "vision", "position"
    coordinates: Optional[Tuple[int, int]]
    selector: Optional[str]
    confidence: float
```

#### 9.2.5 `browser_agent/recording/version_control.py`

```python
class RecordingVersionControl:
    """Version tracking for recordings."""
    
    async def save_version(
        self,
        recording: Recording,
        change_description: Optional[str] = None,
    ) -> Recording:
        """Save a new version of a recording."""
    
    async def get_version(self, recording_id: str, version: int) -> Optional[Recording]:
        """Get a specific version."""
    
    async def get_latest(self, recording_id: str) -> Optional[Recording]:
        """Get latest version."""
    
    async def list_versions(self, recording_id: str) -> List[RecordingVersionSummary]:
        """List all versions."""
    
    async def diff(
        self,
        recording_id: str,
        version_a: int,
        version_b: int,
    ) -> RecordingDiff:
        """Compare two versions."""
    
    async def rollback(self, recording_id: str, target_version: int) -> Recording:
        """Rollback to a previous version (creates new version)."""


@dataclass
class RecordingDiff:
    actions_added: List[int]
    actions_removed: List[int]
    actions_modified: List[int]
    parameters_added: List[str]
    parameters_removed: List[str]
    parameters_modified: List[str]
    selectors_changed: List[int]          # Action indices where selectors changed
```

### 9.3 API Endpoints

```
POST   /recordings/start                  # Start recording
POST   /recordings/{id}/stop              # Stop recording
GET    /recordings                        # List recordings
GET    /recordings/{id}                   # Get recording details
PUT    /recordings/{id}                   # Update recording metadata
DELETE /recordings/{id}                   # Delete recording

POST   /recordings/{id}/parameterize      # Auto-detect or manual parameterize
POST   /recordings/{id}/play              # Play recording
POST   /recordings/{id}/dry-run           # Dry run (no execution)

GET    /recordings/{id}/versions          # List versions
GET    /recordings/{id}/versions/{v}      # Get specific version
POST   /recordings/{id}/versions/diff     # Diff two versions
POST   /recordings/{id}/versions/rollback # Rollback to version

GET    /recordings/{id}/runs              # Get execution history
GET    /recordings/{id}/runs/{run_id}     # Get specific run result
```

### 9.4 Configuration

```yaml
recording:
  enabled: true
  store_type: sqlite
  store_path: .recordings/recordings.db
  screenshot_storage: .recordings/screenshots
  
  capture:
    screenshots: true                     # Capture screenshots at each step
    dom_snapshots: true                   # Capture DOM state
    element_context: true                 # Capture element details
    max_screenshot_size_kb: 500           # Compress large screenshots
  
  replay:
    default_mode: adaptive                # strict | adaptive | vision_only
    page_match_threshold: 0.85            # Similarity threshold for page matching
    element_match_threshold: 0.7          # Confidence threshold for element matching
    screenshot_on_failure: true           # Capture screenshot on step failure
    continue_on_failure: false            # Continue replay after step failure
  
  version_control:
    max_versions: 50                      # Max versions per recording
    auto_version: true                    # Auto-create version on changes
```

### 9.5 Tests

```
tests/test_recording/
├── test_recorder.py                # 15 tests — start, stop, pause, action capture
├── test_parameterizer.py           # 12 tests — auto-detect, parameterize, validate
├── test_player.py                  # 15 tests — play, play_step, dry_run, strict mode
├── test_adaptive_replay.py         # 12 tests — page matching, element finding, fallback
├── test_version_control.py         # 10 tests — save, diff, rollback
├── test_recording_integration.py   # 10 tests — full record → parameterize → replay cycle
└── test_recording_api.py           # 15 tests — API endpoints
```

### 9.6 Tasks

| # | Task | Est. | Status |
|---|------|------|--------|
| 12.1 | Implement `RecordedAction`, `Recording`, `RecordingParameter` dataclasses | 1d | [x] |
| 12.2 | Implement `WorkflowRecorder` — start, stop, record_action | 1.5d | [x] |
| 12.3 | Implement `RecordingParameterizer` — auto-detect, parameterize | 1.5d | [x] |
| 12.4 | Implement `WorkflowPlayer` — play, play_step, dry_run | 2d | [x] |
| 12.5 | Implement `AdaptiveReplay` — page matching, element finding | 2d | [x] |
| 12.6 | Implement `RecordingVersionControl` — save, diff, rollback | 1.5d | [x] |
| 12.7 | Integrate recording into `BrowserAgent` | 1d | [x] |
| 12.8 | Integrate recording with skill system | 0.5d | [x] |
| 12.9 | Add recording API endpoints | 1d | [x] |
| 12.10 | Write config schema | 0.5d | [x] |
| 12.11 | Write all tests | 2.5d | [x] |

**Total: ~15 days**

---

## 10. Testing Strategy

### 10.1 Test Pyramid

```
                    ╱╲
                   ╱  ╲
                  ╱ E2E ╲                 ← 10% — Full system tests
                 ╱  Tests  ╲                 (Docker, real browser, real LLM)
                ╱────────────╲
               ╱              ╲
              ╱  Integration   ╲           ← 30% — Cross-module tests
             ╱    Tests         ╲            (Governance + Audit + DLP flow)
            ╱────────────────────╲
           ╱                      ╲
          ╱     Unit Tests          ╲       ← 60% — Per-module tests
         ╱    (mocked deps)           ╲       (Fast, isolated, deterministic)
        ╱──────────────────────────────╲
```

### 10.2 Test Categories

| Category | Count (est.) | Description |
|----------|-------------|-------------|
| Unit tests | ~400 | Per-module, mocked dependencies |
| Integration tests | ~80 | Cross-module, some real components |
| API tests | ~120 | HTTP endpoint tests |
| E2E tests | ~20 | Full system with real browser |
| Security tests | ~30 | Credential leak, DLP bypass, isolation |
| Performance tests | ~10 | Throughput, latency under load |

### 10.3 Test Infrastructure

```
tests/
├── test_security/
│   ├── test_crypto.py
│   ├── test_credential_vault.py
│   ├── test_secret_providers.py
│   ├── test_credential_injection.py
│   ├── test_credential_api.py
│   ├── test_pii_detector.py
│   ├── test_redaction.py
│   ├── test_dlp_engine.py
│   ├── test_dlp_integration.py
│   └── test_dlp_api.py
│
├── test_compliance/
│   ├── test_audit_log.py
│   ├── test_chain.py
│   ├── test_audit_store.py
│   ├── test_data_classifier.py
│   ├── test_export.py
│   ├── test_siem.py
│   ├── test_compliance_report.py
│   └── test_audit_api.py
│
├── test_governance/
│   ├── test_policy_engine.py
│   ├── test_approval.py
│   ├── test_notifiers.py
│   ├── test_gates.py
│   ├── test_policy_templates.py
│   ├── test_governance_integration.py
│   └── test_governance_api.py
│
├── test_scheduling/
│   ├── test_cron_schedule.py
│   ├── test_recurring_task.py
│   ├── test_scheduler.py
│   ├── test_health_monitor.py
│   ├── test_business_calendar.py
│   └── test_scheduling_api.py
│
├── test_orchestration/
│   ├── test_tenant_manager.py
│   ├── test_resource_pool.py
│   ├── test_fair_scheduler.py
│   ├── test_quotas.py
│   ├── test_metering.py
│   ├── test_tenant_middleware.py
│   ├── test_isolation.py
│   └── test_orchestration_api.py
│
├── test_recording/
│   ├── test_recorder.py
│   ├── test_parameterizer.py
│   ├── test_player.py
│   ├── test_adaptive_replay.py
│   ├── test_version_control.py
│   ├── test_recording_integration.py
│   └── test_recording_api.py
│
├── test_enterprise_e2e/
│   ├── test_full_credential_workflow.py
│   ├── test_full_compliance_workflow.py
│   ├── test_full_governance_workflow.py
│   ├── test_full_scheduling_workflow.py
│   ├── test_full_dlp_workflow.py
│   ├── test_full_multi_tenant_workflow.py
│   └── test_full_recording_workflow.py
│
└── conftest.py                           # Shared fixtures
```

### 10.4 Test Fixtures

```python
# conftest.py additions

@pytest.fixture
def crypto_engine():
    """Test crypto engine with known key."""
    return CryptoEngine(master_key=b'test-key-32-bytes-long-enough!!')

@pytest.fixture
def credential_vault(crypto_engine, tmp_path):
    """Test credential vault with file store."""
    store = FileCredentialStore(path=str(tmp_path / "creds"))
    return CredentialVault(crypto_engine, store)

@pytest.fixture
def audit_log(tmp_path):
    """Test audit log with file store."""
    store = SQLiteAuditStore(path=str(tmp_path / "audit.db"))
    chain = AuditChain(signing_key=b'test-chain-key-32-bytes-ok!')
    return AuditLog(store, chain)

@pytest.fixture
def policy_engine(audit_log):
    """Test policy engine with sample rules."""
    return PolicyEngine(rules=PolicyTemplates.production_only_approve(...), audit_log=audit_log)

@pytest.fixture
def pii_detector():
    """Test PII detector with built-in patterns."""
    return PIIDetector()

@pytest.fixture
def dlp_engine(pii_detector, audit_log):
    """Test DLP engine."""
    redactor = DataRedactor()
    policy = DLPPolicy(action=DLPAction.REDACT)
    return DLPEngine(pii_detector, redactor, policy, audit_log)

@pytest.fixture
def tenant_manager(tmp_path):
    """Test tenant manager."""
    return TenantManager(store=SQLiteTenantStore(path=str(tmp_path / "tenants.db")))
```

---

## 11. Timeline

### 11.1 Gantt Chart

```
Week  1  2  3  4  5  6  7  8  9  10 11 12 13 14
      ├──┤                                              Phase 6: Credential Vault
         ├─────┤                                        Phase 7: Audit Trail
               ├─────┤                                  Phase 8: Governance
                     ├──┤                               Phase 9: Scheduling
                        ├─────┤                         Phase 10: DLP
                              ├───────────┤             Phase 11: Multi-Tenant
                                           ├───────────┤Phase 12: Recording & Replay
```

### 11.2 Milestones

| Week | Milestone | Deliverables |
|------|-----------|-------------|
| 2 | **M1: Security Foundation** | Credential vault working, tests pass, API endpoints |
| 4 | **M2: Compliance Ready** | Audit trail, chain verification, SIEM export |
| 6 | **M3: Governed Agent** | Policy engine, approval workflows, Slack/Teams notifications |
| 7 | **M4: Scheduled Operations** | Cron scheduler, health monitoring, checkpoint resume |
| 9 | **M5: Data Safe** | DLP engine, PII detection, redaction, LLM prompt scanning |
| 11 | **M6: Multi-Tenant Platform** | Tenant isolation, fair scheduler, resource pool, metering |
| 14 | **M7: Record & Replay** | Workflow recorder, adaptive replay, version control |

### 11.3 Parallelization

Some phases can overlap because they're mostly independent:

- **Phase 6 + 7** can run in parallel (different modules, shared crypto)
- **Phase 8** starts after Phase 6/7 foundations are in place
- **Phase 9** is lightweight and can overlap with Phase 8
- **Phase 10** depends on Phase 7's data classifier
- **Phase 11** depends on 6, 7, 8 (tenant scoping)
- **Phase 12** is independent and can start in Week 11

---

## 12. Dependencies

### 12.1 New Python Dependencies

| Package | Phase | Purpose |
|---------|-------|---------|
| `cryptography>=42.0` | 6 | AES-256-GCM encryption |
| `hvac>=2.0` | 6 | HashiCorp Vault client (optional) |
| `boto3>=1.34` | 6 | AWS Secrets Manager (optional) |
| `azure-identity>=1.15` | 6 | Azure Key Vault auth (optional) |
| `azure-keyvault-secrets>=4.8` | 6 | Azure Key Vault client (optional) |
| `croniter>=1.4` | 9 | Cron expression parsing |
| `holidays>=0.45` | 9 | Holiday calendar support |
| `pytz>=2024.1` | 9 | Timezone support |
| `aiosqlite>=0.19` | 7,8,9,11,12 | Async SQLite |
| `psycopg2-binary>=2.9` | 7,11 | PostgreSQL (optional) |
| `Pillow>=10.0` | 10,12 | Screenshot DLP / comparison |
| `pytesseract>=0.3` | 10 | OCR for screenshot DLP (optional) |

### 12.2 Updated requirements.txt

```txt
# Existing
playwright>=1.40.0
aiohttp>=3.9.0
pyyaml>=6.0
pydantic>=2.0.0
tenacity>=8.2.0
pillow>=10.0.0
fastapi>=0.109.0

# New — Enterprise Features
cryptography>=42.0
aiosqlite>=0.19
croniter>=1.4
holidays>=0.45
pytz>=2024.1

# Optional — External Integrations
hvac>=2.0                     # HashiCorp Vault
boto3>=1.34                   # AWS Secrets Manager
azure-identity>=1.15          # Azure Key Vault
azure-keyvault-secrets>=4.8   # Azure Key Vault
psycopg2-binary>=2.9          # PostgreSQL audit store
pytesseract>=0.3              # OCR for screenshot DLP
```

---

## 13. Risk Assessment

### 13.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Encryption key management is complex | Medium | High | Start with env var key, document HSM integration |
| DLP regex patterns have false positives | High | Medium | Tunable confidence thresholds, whitelist support |
| Multi-tenant browser isolation leaks | Low | Critical | Comprehensive isolation tests, security audit |
| Approval workflow creates deadlocks | Medium | Medium | Timeout + escalation, deadlock detection |
| Adaptive replay fails on heavily dynamic pages | Medium | Medium | Vision-only fallback mode, manual intervention |
| Scheduler drift on long-running tasks | Low | Low | Clock sync, jitter tolerance |

### 13.2 Scope Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| 14 weeks is too aggressive for 7 features | Medium | High | Each phase is independently shippable |
| External provider integrations take longer | Medium | Medium | Start with built-in providers, external are optional |
| API surface grows too large | Low | Medium | V2 API in separate module, versioned endpoints |
| Test coverage insufficient | Medium | High | Tests written alongside code (TDD approach) |

### 13.3 Mitigation Strategy

1. **Ship incrementally** — Each phase produces working, testable, shippable features
2. **Feature flags** — All new features are behind config flags (`security.credential_vault.enabled: false`)
3. **Backward compatibility** — Existing API and behavior unchanged when features are disabled
4. **External providers are optional** — All have local/file fallbacks
5. **Comprehensive tests** — Test count target: 660+ (up from 573)

---

## Summary

| Phase | Feature | Duration | New Files | Tests | Est. Tasks |
|-------|---------|----------|-----------|-------|------------|
| 6 | Credential Vault | 2 weeks | 4 | 72 | 15 |
| 7 | Audit Trail | 2 weeks | 5 | 88 | 15 |
| 8 | Approval Workflows | 2 weeks | 5 | 88 | 14 |
| 9 | Scheduled Workflows | 1.5 weeks | 4 | 67 | 10 |
| 10 | DLP | 1.5 weeks | 3 | 68 | 11 |
| 11 | Multi-Tenant | 2.5 weeks | 5 | 100 | 11 |
| 12 | Recording & Replay | 2.5 weeks | 5 | 89 | 11 |
| **Total** | | **14 weeks** | **31 files** | **~572 tests** | **87 tasks** |

After completion, b-agent will be the **only open-source browser automation framework** with:
- ✅ Encrypted credential management
- ✅ SOC2/HIPPA/GDPR-compliant audit trail
- ✅ Human-in-the-loop governance
- ✅ Scheduled recurring workflows
- ✅ Built-in data loss prevention
- ✅ Multi-tenant isolation
- ✅ RPA-style record & replay with AI self-healing

This positions b-agent as the **enterprise platform** that wraps around UI-TARS-desktop's vision model — not competing with it, but making it deployable in environments where Bytedance's tool can't go.
