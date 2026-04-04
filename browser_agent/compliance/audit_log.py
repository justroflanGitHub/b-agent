"""Immutable, tamper-evident audit trail.

Every action the agent takes is recorded with cryptographic chaining
(hash of previous event stored in current event) so the log cannot
be tampered with undetectably.
"""

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .chain import AuditChain

logger = logging.getLogger(__name__)


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
    ACTION_BLOCKED = "action.blocked"

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
    DATA_DELETED = "data.deleted"

    # System
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    BROWSER_OPENED = "browser.opened"
    BROWSER_CLOSED = "browser.closed"
    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_RESTORED = "checkpoint.restored"
    RECOVERY_TRIGGERED = "recovery.triggered"

    # DLP
    DLP_VIOLATION = "dlp.violation"
    DLP_REDACTED = "dlp.redacted"


class SensitivityLevel(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


@dataclass
class AuditEvent:
    """A single audit trail entry."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: AuditEventType = AuditEventType.ACTION_EXECUTED
    tenant_id: str = "default"
    user_id: str = "system"
    task_id: Optional[str] = None
    step_index: Optional[int] = None

    # What happened
    action_type: Optional[str] = None
    target_url: Optional[str] = None
    target_element: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Outcome
    outcome: str = "success"  # success, failure, blocked, redacted

    # Error
    error_message: Optional[str] = None

    # Data classification
    data_sensitivity: Optional[SensitivityLevel] = None
    data_categories: List[str] = field(default_factory=list)

    # Cryptographic chain
    previous_hash: str = ""
    event_hash: str = ""
    chain_signature: str = ""

    # Context
    session_id: Optional[str] = None
    agent_id: Optional[str] = None

    # Screenshot reference
    screenshot_hash: Optional[str] = None

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of event fields (excluding chain fields)."""
        payload = {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "task_id": self.task_id,
            "step_index": self.step_index,
            "action_type": self.action_type,
            "target_url": self.target_url,
            "target_element": self.target_element,
            "parameters": self.parameters,
            "outcome": self.outcome,
            "error_message": self.error_message,
            "data_sensitivity": self.data_sensitivity.value if self.data_sensitivity else None,
            "data_categories": self.data_categories,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "screenshot_hash": self.screenshot_hash,
            "previous_hash": self.previous_hash,
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "task_id": self.task_id,
            "step_index": self.step_index,
            "action_type": self.action_type,
            "target_url": self.target_url,
            "target_element": self.target_element,
            "parameters": self.parameters,
            "outcome": self.outcome,
            "error_message": self.error_message,
            "data_sensitivity": self.data_sensitivity.value if self.data_sensitivity else None,
            "data_categories": self.data_categories,
            "previous_hash": self.previous_hash,
            "event_hash": self.event_hash,
            "chain_signature": self.chain_signature,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "screenshot_hash": self.screenshot_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuditEvent":
        """Deserialize from storage."""
        ds = data.get("data_sensitivity")
        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=AuditEventType(data["event_type"]),
            tenant_id=data.get("tenant_id", "default"),
            user_id=data.get("user_id", "system"),
            task_id=data.get("task_id"),
            step_index=data.get("step_index"),
            action_type=data.get("action_type"),
            target_url=data.get("target_url"),
            target_element=data.get("target_element"),
            parameters=data.get("parameters", {}),
            outcome=data.get("outcome", "success"),
            error_message=data.get("error_message"),
            data_sensitivity=SensitivityLevel(ds) if ds else None,
            data_categories=data.get("data_categories", []),
            previous_hash=data.get("previous_hash", ""),
            event_hash=data.get("event_hash", ""),
            chain_signature=data.get("chain_signature", ""),
            session_id=data.get("session_id"),
            agent_id=data.get("agent_id"),
            screenshot_hash=data.get("screenshot_hash"),
        )


@dataclass
class AuditFilter:
    """Filter for querying audit events."""

    tenant_id: Optional[str] = None
    event_types: Optional[List[AuditEventType]] = None
    task_id: Optional[str] = None
    user_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    sensitivity: Optional[SensitivityLevel] = None
    limit: int = 100
    offset: int = 0


@dataclass
class TaskTimeline:
    """Full timeline of events for a task."""

    task_id: str
    events: List[AuditEvent]
    total_duration: Optional[float] = None
    action_count: int = 0
    success_count: int = 0
    failure_count: int = 0


@dataclass
class ComplianceReport:
    """Generated compliance report."""

    framework: str
    tenant_id: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_events: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    actions_executed: int = 0
    credential_accesses: int = 0
    policy_evaluations: int = 0
    approval_requests: int = 0
    dlp_violations: int = 0
    data_extractions: int = 0
    chain_integrity: bool = True
    findings: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "framework": self.framework,
            "tenant_id": self.tenant_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "total_events": self.total_events,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "actions_executed": self.actions_executed,
            "credential_accesses": self.credential_accesses,
            "policy_evaluations": self.policy_evaluations,
            "approval_requests": self.approval_requests,
            "dlp_violations": self.dlp_violations,
            "data_extractions": self.data_extractions,
            "chain_integrity": self.chain_integrity,
            "findings": self.findings,
        }


# --- Storage backends ---


class AuditStore:
    """Abstract storage backend for audit events."""

    async def append(self, event: AuditEvent) -> str:
        raise NotImplementedError

    async def query(self, filters: AuditFilter) -> List[AuditEvent]:
        raise NotImplementedError

    async def get_last_event(self, tenant_id: str) -> Optional[AuditEvent]:
        raise NotImplementedError

    async def count(self, filters: AuditFilter) -> int:
        raise NotImplementedError


class SQLiteAuditStore(AuditStore):
    """SQLite storage for audit events."""

    def __init__(self, path: str = ".audit/audit.db"):
        import os

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._path = path
        self._init_db()

    def _init_db(self):
        import sqlite3

        conn = sqlite3.connect(self._path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                user_id TEXT DEFAULT 'system',
                task_id TEXT,
                step_index INTEGER,
                action_type TEXT,
                target_url TEXT,
                target_element TEXT,
                parameters TEXT DEFAULT '{}',
                outcome TEXT DEFAULT 'success',
                error_message TEXT,
                data_sensitivity TEXT,
                data_categories TEXT DEFAULT '[]',
                previous_hash TEXT DEFAULT '',
                event_hash TEXT DEFAULT '',
                chain_signature TEXT DEFAULT '',
                session_id TEXT,
                agent_id TEXT,
                screenshot_hash TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_events(tenant_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_task ON audit_events(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type)")
        conn.commit()
        conn.close()

    def _get_conn(self):
        import sqlite3

        return sqlite3.connect(self._path)

    def _event_to_row(self, event: AuditEvent) -> tuple:
        import json

        return (
            event.event_id,
            event.timestamp.isoformat(),
            event.event_type.value,
            event.tenant_id,
            event.user_id,
            event.task_id,
            event.step_index,
            event.action_type,
            event.target_url,
            event.target_element,
            json.dumps(event.parameters, default=str),
            event.outcome,
            event.error_message,
            event.data_sensitivity.value if event.data_sensitivity else None,
            json.dumps(event.data_categories),
            event.previous_hash,
            event.event_hash,
            event.chain_signature,
            event.session_id,
            event.agent_id,
            event.screenshot_hash,
        )

    def _row_to_event(self, row: tuple) -> AuditEvent:
        import json

        ds = row[13]
        return AuditEvent(
            event_id=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            event_type=AuditEventType(row[2]),
            tenant_id=row[3],
            user_id=row[4],
            task_id=row[5],
            step_index=row[6],
            action_type=row[7],
            target_url=row[8],
            target_element=row[9],
            parameters=json.loads(row[10]),
            outcome=row[11],
            error_message=row[12],
            data_sensitivity=SensitivityLevel(ds) if ds else None,
            data_categories=json.loads(row[14]),
            previous_hash=row[15] or "",
            event_hash=row[16] or "",
            chain_signature=row[17] or "",
            session_id=row[18],
            agent_id=row[19],
            screenshot_hash=row[20],
        )

    async def append(self, event: AuditEvent) -> str:
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                self._event_to_row(event),
            )
            conn.commit()
            return event.event_id
        finally:
            conn.close()

    async def query(self, filters: AuditFilter) -> List[AuditEvent]:
        conn = self._get_conn()
        try:
            clauses = []
            params = []
            if filters.tenant_id:
                clauses.append("tenant_id = ?")
                params.append(filters.tenant_id)
            if filters.task_id:
                clauses.append("task_id = ?")
                params.append(filters.task_id)
            if filters.user_id:
                clauses.append("user_id = ?")
                params.append(filters.user_id)
            if filters.event_types:
                placeholders = ",".join("?" * len(filters.event_types))
                clauses.append(f"event_type IN ({placeholders})")
                params.extend(e.value for e in filters.event_types)
            if filters.start_time:
                clauses.append("timestamp >= ?")
                params.append(filters.start_time.isoformat())
            if filters.end_time:
                clauses.append("timestamp <= ?")
                params.append(filters.end_time.isoformat())
            if filters.sensitivity:
                clauses.append("data_sensitivity = ?")
                params.append(filters.sensitivity.value)

            where = " AND ".join(clauses) if clauses else "1=1"
            sql = f"SELECT * FROM audit_events WHERE {where} ORDER BY timestamp ASC LIMIT ? OFFSET ?"
            params.extend([filters.limit, filters.offset])

            cursor = conn.execute(sql, params)
            return [self._row_to_event(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    async def get_last_event(self, tenant_id: str) -> Optional[AuditEvent]:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM audit_events WHERE tenant_id=? ORDER BY timestamp DESC LIMIT 1",
                (tenant_id,),
            )
            row = cursor.fetchone()
            return self._row_to_event(row) if row else None
        finally:
            conn.close()

    async def count(self, filters: AuditFilter) -> int:
        conn = self._get_conn()
        try:
            clauses = []
            params = []
            if filters.tenant_id:
                clauses.append("tenant_id = ?")
                params.append(filters.tenant_id)
            if filters.task_id:
                clauses.append("task_id = ?")
                params.append(filters.task_id)
            if filters.start_time:
                clauses.append("timestamp >= ?")
                params.append(filters.start_time.isoformat())
            if filters.end_time:
                clauses.append("timestamp <= ?")
                params.append(filters.end_time.isoformat())

            where = " AND ".join(clauses) if clauses else "1=1"
            cursor = conn.execute(f"SELECT COUNT(*) FROM audit_events WHERE {where}", params)
            return cursor.fetchone()[0]
        finally:
            conn.close()


class FileAuditStore(AuditStore):
    """Append-only JSONL file for simple deployments."""

    def __init__(self, path: str = ".audit"):
        import os

        os.makedirs(path, exist_ok=True)
        self._path = path

    def _tenant_file(self, tenant_id: str) -> str:
        import os

        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in tenant_id)
        return os.path.join(self._path, f"audit_{safe}.jsonl")

    async def append(self, event: AuditEvent) -> str:
        import json

        with open(self._tenant_file(event.tenant_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), default=str) + "\n")
        return event.event_id

    async def query(self, filters: AuditFilter) -> List[AuditEvent]:
        import json
        import os

        tenant = filters.tenant_id or "default"
        path = self._tenant_file(tenant)
        if not os.path.exists(path):
            return []

        events = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    event = AuditEvent.from_dict(data)
                    if self._matches(event, filters):
                        events.append(event)
                except (json.JSONDecodeError, KeyError):
                    continue

        events.sort(key=lambda e: e.timestamp)
        return events[filters.offset : filters.offset + filters.limit]

    async def get_last_event(self, tenant_id: str) -> Optional[AuditEvent]:
        events = await self.query(AuditFilter(tenant_id=tenant_id, limit=1))
        if not events:
            return None
        # Need the LAST event, so reverse the query
        import json
        import os

        path = self._tenant_file(tenant_id)
        if not os.path.exists(path):
            return None

        last_line = None
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line.strip()

        if last_line:
            return AuditEvent.from_dict(json.loads(last_line))
        return None

    async def count(self, filters: AuditFilter) -> int:
        return len(await self.query(filters))

    @staticmethod
    def _matches(event: AuditEvent, f: AuditFilter) -> bool:
        if f.task_id and event.task_id != f.task_id:
            return False
        if f.user_id and event.user_id != f.user_id:
            return False
        if f.event_types and event.event_type not in f.event_types:
            return False
        if f.start_time and event.timestamp < f.start_time:
            return False
        if f.end_time and event.timestamp > f.end_time:
            return False
        if f.sensitivity and event.data_sensitivity != f.sensitivity:
            return False
        return True


class AuditLog:
    """Immutable, append-only audit trail with cryptographic chaining."""

    def __init__(self, store: AuditStore, chain: AuditChain):
        self._store = store
        self._chain = chain

    @classmethod
    def from_config(cls, config: dict) -> "AuditLog":
        """Create from config dict."""
        import os
        import base64

        store_type = config.get("store_type", "sqlite")
        store_path = config.get("store_path", ".audit")

        if store_type == "file":
            store = FileAuditStore(store_path)
        else:
            db_path = os.path.join(store_path, "audit.db") if store_type == "sqlite" else store_path
            store = SQLiteAuditStore(db_path)

        chain_key_str = os.environ.get(config.get("chain_key_env", "AUDIT_CHAIN_KEY"))
        if chain_key_str:
            chain_key = base64.b64decode(chain_key_str)
        else:
            chain_key = os.urandom(32)

        chain = AuditChain(signing_key=chain_key)
        return cls(store, chain)

    async def record(
        self,
        event_type,
        tenant_id: str = "default",
        user_id: str = "system",
        task_id: Optional[str] = None,
        step_index: Optional[int] = None,
        action_type: Optional[str] = None,
        target_url: Optional[str] = None,
        target_element: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        outcome: str = "success",
        error_message: Optional[str] = None,
        data_sensitivity: Optional[SensitivityLevel] = None,
        data_categories: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        screenshot_hash: Optional[str] = None,
    ) -> AuditEvent:
        """Record an audit event with chain linking."""
        # Accept string event types
        if isinstance(event_type, str):
            event_type = AuditEventType(event_type)

        # Get previous hash for this tenant
        prev_event = await self._store.get_last_event(tenant_id)
        previous_hash = prev_event.event_hash if prev_event else "GENESIS"

        event = AuditEvent(
            event_type=event_type,
            tenant_id=tenant_id,
            user_id=user_id,
            task_id=task_id,
            step_index=step_index,
            action_type=action_type,
            target_url=target_url,
            target_element=target_element,
            parameters=parameters or {},
            outcome=outcome,
            error_message=error_message,
            data_sensitivity=data_sensitivity,
            data_categories=data_categories or [],
            session_id=session_id,
            agent_id=agent_id,
            screenshot_hash=screenshot_hash,
            previous_hash=previous_hash,
        )

        # Link to chain (compute hash + sign)
        event = self._chain.link(event)

        # Persist
        await self._store.append(event)

        logger.debug(
            "Audit: %s tenant=%s task=%s outcome=%s",
            event_type.value,
            tenant_id,
            task_id,
            outcome,
        )

        return event

    async def query(self, filters: AuditFilter) -> List[AuditEvent]:
        """Query audit events with filters."""
        return await self._store.query(filters)

    async def get_task_timeline(self, task_id: str, tenant_id: str = "default") -> TaskTimeline:
        """Get full timeline of events for a task."""
        events = await self._store.query(
            AuditFilter(
                tenant_id=tenant_id,
                task_id=task_id,
                limit=10000,
            )
        )

        success = sum(1 for e in events if e.outcome == "success")
        failure = sum(1 for e in events if e.outcome == "failure")
        duration = None
        task_events = [
            e
            for e in events
            if e.event_type in (AuditEventType.TASK_STARTED, AuditEventType.TASK_COMPLETED, AuditEventType.TASK_FAILED)
        ]
        if len(task_events) >= 2:
            start = task_events[0].timestamp
            end = task_events[-1].timestamp
            duration = (end - start).total_seconds()

        return TaskTimeline(
            task_id=task_id,
            events=events,
            total_duration=duration,
            action_count=len(
                [
                    e
                    for e in events
                    if e.event_type
                    in (AuditEventType.ACTION_EXECUTED, AuditEventType.ACTION_SUCCEEDED, AuditEventType.ACTION_FAILED)
                ]
            ),
            success_count=success,
            failure_count=failure,
        )

    async def verify_chain(self, tenant_id: str) -> "ChainVerificationResult":
        """Verify integrity of the entire audit chain for a tenant."""
        events = await self._store.query(
            AuditFilter(
                tenant_id=tenant_id,
                limit=100000,
            )
        )
        return self._chain.verify(events)

    async def generate_compliance_report(
        self,
        framework: str,
        start_date: datetime,
        end_date: datetime,
        tenant_id: str = "default",
    ) -> ComplianceReport:
        """Generate a compliance report for a time period."""
        events = await self._store.query(
            AuditFilter(
                tenant_id=tenant_id,
                start_time=start_date,
                end_time=end_date,
                limit=100000,
            )
        )

        report = ComplianceReport(
            framework=framework,
            tenant_id=tenant_id,
            period_start=start_date,
            period_end=end_date,
            total_events=len(events),
        )

        type_counts = {}
        for e in events:
            type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1

        report.total_tasks = type_counts.get(AuditEventType.TASK_CREATED, 0)
        report.completed_tasks = type_counts.get(AuditEventType.TASK_COMPLETED, 0)
        report.failed_tasks = type_counts.get(AuditEventType.TASK_FAILED, 0)
        report.actions_executed = type_counts.get(AuditEventType.ACTION_EXECUTED, 0)
        report.credential_accesses = type_counts.get(AuditEventType.CREDENTIAL_ACCESSED, 0)
        report.policy_evaluations = type_counts.get(AuditEventType.POLICY_EVALUATED, 0)
        report.approval_requests = type_counts.get(AuditEventType.APPROVAL_REQUESTED, 0)
        report.dlp_violations = type_counts.get(AuditEventType.DLP_VIOLATION, 0)
        report.data_extractions = type_counts.get(AuditEventType.DATA_EXTRACTED, 0)

        # Verify chain integrity
        chain_result = await self.verify_chain(tenant_id)
        report.chain_integrity = chain_result.is_valid

        # Findings
        if report.failed_tasks > report.completed_tasks:
            report.findings.append(
                {
                    "severity": "warning",
                    "message": f"More tasks failed ({report.failed_tasks}) than completed ({report.completed_tasks})",
                }
            )
        if report.dlp_violations > 0:
            report.findings.append(
                {
                    "severity": "critical",
                    "message": f"{report.dlp_violations} DLP violations detected",
                }
            )
        if not report.chain_integrity:
            report.findings.append(
                {
                    "severity": "critical",
                    "message": "Audit chain integrity verification failed — possible tampering",
                }
            )

        return report
