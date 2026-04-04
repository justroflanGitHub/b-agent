"""Cryptographic hash chain for tamper-evident audit log.

Each event's hash includes the previous event's hash, forming a chain.
The chain is signed with HMAC-SHA256 so tampering with any event
breaks the chain signature.
"""

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TamperedEvent:
    """Details of a tampered event in the chain."""

    event_id: str
    expected_hash: str
    actual_hash: str
    issue: str  # "hash_mismatch", "signature_invalid", "chain_broken"


@dataclass
class MissingEvent:
    """A gap in the chain."""

    after_event_id: str
    expected_hash: str
    got_hash: str


@dataclass
class ChainVerificationResult:
    """Result of verifying the entire audit chain."""

    total_events: int
    verified_events: int = 0
    tampered_events: List[TamperedEvent] = field(default_factory=list)
    missing_events: List[MissingEvent] = field(default_factory=list)
    is_valid: bool = True
    verification_time: float = 0.0


class AuditChain:
    """Cryptographic hash chain for tamper-evident audit log.

    Uses SHA-256 for event hashing and HMAC-SHA256 for chain signatures.
    """

    def __init__(self, signing_key: bytes):
        if len(signing_key) < 16:
            raise ValueError("Signing key must be at least 16 bytes")
        self._signing_key = signing_key

    def link(self, event) -> "AuditEvent":
        """Link an event to the chain.

        Computes event hash and HMAC signature.

        Args:
            event: AuditEvent with previous_hash already set.

        Returns:
            The same event with event_hash and chain_signature populated.
        """
        # Compute event hash
        event.event_hash = event.compute_hash()

        # Sign: HMAC of (event_hash + previous_hash)
        msg = f"{event.event_hash}:{event.previous_hash}".encode("utf-8")
        event.chain_signature = hmac.new(self._signing_key, msg, hashlib.sha256).hexdigest()

        return event

    def verify(self, events: list) -> ChainVerificationResult:
        """Verify entire chain integrity.

        Checks:
        1. Each event's hash is correctly computed
        2. Previous hash linkage is correct
        3. HMAC signatures are valid
        4. No gaps in the chain

        Args:
            events: List of AuditEvent objects, sorted by timestamp.
        """
        import time

        start = time.monotonic()

        result = ChainVerificationResult(total_events=len(events))
        verified = 0

        for i, event in enumerate(events):
            # Check hash
            expected_hash = event.compute_hash()
            if event.event_hash != expected_hash:
                result.tampered_events.append(
                    TamperedEvent(
                        event_id=event.event_id,
                        expected_hash=expected_hash,
                        actual_hash=event.event_hash,
                        issue="hash_mismatch",
                    )
                )
                result.is_valid = False
                continue

            # Check chain linkage
            if i == 0:
                if event.previous_hash != "GENESIS":
                    result.tampered_events.append(
                        TamperedEvent(
                            event_id=event.event_id,
                            expected_hash="GENESIS",
                            actual_hash=event.previous_hash,
                            issue="chain_broken",
                        )
                    )
                    result.is_valid = False
                    continue
            else:
                prev = events[i - 1]
                if event.previous_hash != prev.event_hash:
                    result.missing_events.append(
                        MissingEvent(
                            after_event_id=prev.event_id,
                            expected_hash=prev.event_hash,
                            got_hash=event.previous_hash,
                        )
                    )
                    result.is_valid = False
                    continue

            # Check signature
            msg = f"{event.event_hash}:{event.previous_hash}".encode("utf-8")
            expected_sig = hmac.new(self._signing_key, msg, hashlib.sha256).hexdigest()
            if event.chain_signature != expected_sig:
                result.tampered_events.append(
                    TamperedEvent(
                        event_id=event.event_id,
                        expected_hash=expected_sig,
                        actual_hash=event.chain_signature,
                        issue="signature_invalid",
                    )
                )
                result.is_valid = False
                continue

            verified += 1

        result.verified_events = verified
        result.verification_time = time.monotonic() - start
        return result

    def seal(self, events: list) -> "ChainSeal":
        """Create a periodic seal (Merkle-like checkpoint).

        Produces a root hash over all events since the last seal,
        signed with the chain key.
        """
        if not events:
            raise ValueError("Cannot seal empty event list")

        # Simple Merkle: hash all event hashes together
        combined = ":".join(e.event_hash for e in events)
        merkle_root = hashlib.sha256(combined.encode("utf-8")).hexdigest()

        # Sign the seal
        sig = hmac.new(
            self._signing_key,
            f"SEAL:{merkle_root}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return ChainSeal(
            merkle_root=merkle_root,
            event_count=len(events),
            first_event_id=events[0].event_id,
            last_event_id=events[-1].event_id,
            signature=sig,
        )


@dataclass
class ChainSeal:
    """Periodic seal over a batch of events."""

    seal_id: str = ""
    merkle_root: str = ""
    event_count: int = 0
    first_event_id: str = ""
    last_event_id: str = ""
    signature: str = ""
    created_at: Optional[object] = None

    def __post_init__(self):
        if not self.seal_id:
            import uuid

            self.seal_id = str(uuid.uuid4())
        if self.created_at is None:
            from datetime import datetime, timezone

            self.created_at = datetime.now(timezone.utc)

    def verify(self, signing_key: bytes, events: list) -> bool:
        """Verify this seal against the original events and signing key."""
        import hmac as hmac_mod
        import hashlib as hl

        # Recompute merkle root
        combined = ":".join(e.event_hash for e in events)
        expected_root = hl.sha256(combined.encode("utf-8")).hexdigest()

        if expected_root != self.merkle_root:
            return False

        # Verify signature
        expected_sig = hmac_mod.new(
            signing_key,
            f"SEAL:{self.merkle_root}".encode("utf-8"),
            hl.sha256,
        ).hexdigest()

        return expected_sig == self.signature
