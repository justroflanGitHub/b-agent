"""Security module — credential vault, DLP, and encryption utilities."""

from .crypto import CryptoEngine, EncryptedBlob
from .credential_vault import (
    CredentialVault,
    CredentialEntry,
    CredentialType,
    RotationPolicy,
    DecryptedCredential,
    CredentialSummary,
)
from .secret_providers import (
    SecretProvider,
    EnvironmentProvider,
    ChainedProvider,
)
from .dlp import (
    PIIDetector,
    PIIType,
    PIIMatch,
    DataRedactor,
    RedactionStrategy,
    DLPEngine,
    DLPPolicy,
    DLPAction,
)

__all__ = [
    "CryptoEngine",
    "EncryptedBlob",
    "CredentialVault",
    "CredentialEntry",
    "CredentialType",
    "RotationPolicy",
    "DecryptedCredential",
    "CredentialSummary",
    "SecretProvider",
    "EnvironmentProvider",
    "ChainedProvider",
    "PIIDetector",
    "PIIType",
    "PIIMatch",
    "DataRedactor",
    "RedactionStrategy",
    "DLPEngine",
    "DLPPolicy",
    "DLPAction",
]
