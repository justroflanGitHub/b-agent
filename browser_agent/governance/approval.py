"""Approval workflow manager.

Manages approval requests, waits for human decisions, and handles
timeouts and escalation.
"""

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .policy_engine import ApprovalConfig, PolicyContext

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"


@dataclass
class ApprovalRequest:
    """An approval request."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    step_index: int = 0
    rule_id: str = ""
    context: Optional[PolicyContext] = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    requested_by: str = "system"
    approvers: List[str] = field(default_factory=list)
    approval_config: Optional[ApprovalConfig] = None
    expires_at: Optional[datetime] = None

    # State snapshot for resumption
    checkpoint_id: Optional[str] = None
    browser_state: Dict[str, Any] = field(default_factory=dict)

    # Resolution
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None

    # Escalation
    escalated_at: Optional[datetime] = None
    escalation_level: int = 0

    # Description for human reviewers
    description: str = ""

    def __post_init__(self):
        if self.expires_at is None and self.approval_config:
            timeout = self.approval_config.timeout_seconds or 3600
            self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=timeout)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "task_id": self.task_id,
            "step_index": self.step_index,
            "rule_id": self.rule_id,
            "status": self.status.value,
            "requested_at": self.requested_at.isoformat(),
            "requested_by": self.requested_by,
            "approvers": self.approvers,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
            "escalation_level": self.escalation_level,
            "description": self.description,
            "context": self.context.to_dict() if self.context else None,
        }


class ApprovalStore:
    """Storage backend for approval requests."""

    def __init__(self, path: str = ".governance/approvals.db"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._path = path
        self._init_db()

    def _init_db(self):
        import sqlite3

        conn = sqlite3.connect(self._path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approval_requests (
                request_id TEXT PRIMARY KEY,
                task_id TEXT,
                step_index INTEGER,
                rule_id TEXT,
                status TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                requested_by TEXT DEFAULT 'system',
                approvers TEXT DEFAULT '[]',
                expires_at TEXT,
                resolved_at TEXT,
                resolved_by TEXT,
                resolution_note TEXT,
                escalation_level INTEGER DEFAULT 0,
                description TEXT,
                context TEXT,
                checkpoint_id TEXT,
                browser_state TEXT DEFAULT '{}'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_approval_task ON approval_requests(task_id)")
        conn.commit()
        conn.close()

    async def save(self, request: ApprovalRequest) -> str:
        import sqlite3

        conn = sqlite3.connect(self._path)
        conn.execute(
            """INSERT OR REPLACE INTO approval_requests VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                request.request_id,
                request.task_id,
                request.step_index,
                request.rule_id,
                request.status.value,
                request.requested_at.isoformat(),
                request.requested_by,
                json.dumps(request.approvers),
                request.expires_at.isoformat() if request.expires_at else None,
                request.resolved_at.isoformat() if request.resolved_at else None,
                request.resolved_by,
                request.resolution_note,
                request.escalation_level,
                request.description,
                json.dumps(request.context.to_dict()) if request.context else None,
                request.checkpoint_id,
                json.dumps(request.browser_state),
            ),
        )
        conn.commit()
        conn.close()
        return request.request_id

    async def load(self, request_id: str) -> Optional[ApprovalRequest]:
        import sqlite3

        conn = sqlite3.connect(self._path)
        cursor = conn.execute("SELECT * FROM approval_requests WHERE request_id=?", (request_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_request(row)

    async def update(self, request: ApprovalRequest) -> bool:
        await self.save(request)
        return True

    async def list_by_status(self, status: ApprovalStatus) -> List[ApprovalRequest]:
        import sqlite3

        conn = sqlite3.connect(self._path)
        cursor = conn.execute("SELECT * FROM approval_requests WHERE status=?", (status.value,))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_request(r) for r in rows]

    async def list_pending(self, approver: Optional[str] = None) -> List[ApprovalRequest]:
        import sqlite3

        conn = sqlite3.connect(self._path)
        if approver:
            cursor = conn.execute(
                "SELECT * FROM approval_requests WHERE status='pending' AND approvers LIKE ?",
                (f"%{approver}%",),
            )
        else:
            cursor = conn.execute("SELECT * FROM approval_requests WHERE status='pending'")
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_request(r) for r in rows]

    def _row_to_request(self, row: tuple) -> ApprovalRequest:
        ctx_data = json.loads(row[14]) if row[14] else None
        context = PolicyContext(**ctx_data) if ctx_data else None

        req = ApprovalRequest(
            request_id=row[0],
            task_id=row[1] or "",
            step_index=row[2] or 0,
            rule_id=row[3] or "",
            status=ApprovalStatus(row[4]),
            requested_at=datetime.fromisoformat(row[5]),
            requested_by=row[6] or "system",
            approvers=json.loads(row[7]),
            expires_at=datetime.fromisoformat(row[8]) if row[8] else None,
            resolved_at=datetime.fromisoformat(row[9]) if row[9] else None,
            resolved_by=row[10],
            resolution_note=row[11],
            escalation_level=row[12] or 0,
            description=row[13] or "",
            context=context,
            checkpoint_id=row[15],
            browser_state=json.loads(row[16]) if row[16] else {},
        )
        return req


class ApprovalManager:
    """Manage approval workflows.

    Supports:
    - Single approver
    - Quorum (N of M)
    - Escalation chains
    - Timeout with auto-deny
    """

    def __init__(self, store: Optional[ApprovalStore] = None, notifiers: Optional[List["Notifier"]] = None):
        self._store = store or ApprovalStore()
        self._notifiers = notifiers or []
        self._pending_events: Dict[str, asyncio.Event] = {}

    async def request_approval(
        self,
        context: PolicyContext,
        rule_id: str = "",
        approval_config: Optional[ApprovalConfig] = None,
        checkpoint_id: Optional[str] = None,
        browser_state: Optional[Dict] = None,
        requested_by: str = "system",
        description: str = "",
    ) -> ApprovalRequest:
        """Create an approval request and notify approvers."""
        config = approval_config or ApprovalConfig()

        request = ApprovalRequest(
            task_id=context.task_id,
            step_index=context.step_index,
            rule_id=rule_id,
            context=context,
            approvers=config.approvers,
            approval_config=config,
            requested_by=requested_by,
            checkpoint_id=checkpoint_id,
            browser_state=browser_state or {},
            description=description or f"Action requires approval: {context.action_type} on {context.target_url}",
        )

        await self._store.save(request)
        self._pending_events[request.request_id] = asyncio.Event()

        # Notify approvers
        for notifier in self._notifiers:
            try:
                await notifier.send_approval_request(request)
            except Exception as e:
                logger.warning("Failed to notify via %s: %s", type(notifier).__name__, e)

        logger.info(
            "Approval requested: %s for task=%s (approvers=%s)",
            request.request_id,
            context.task_id,
            config.approvers,
        )
        return request

    async def approve(
        self,
        request_id: str,
        approver: str,
        note: Optional[str] = None,
    ) -> ApprovalRequest:
        """Approve a pending request."""
        request = await self._store.load(request_id)
        if request is None:
            raise KeyError(f"Approval request not found: {request_id}")
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request is not pending (status={request.status.value})")

        request.status = ApprovalStatus.APPROVED
        request.resolved_at = datetime.now(timezone.utc)
        request.resolved_by = approver
        request.resolution_note = note

        await self._store.update(request)

        # Signal waiters
        event = self._pending_events.get(request_id)
        if event:
            event.set()

        logger.info("Approved: %s by %s", request_id, approver)
        return request

    async def deny(
        self,
        request_id: str,
        approver: str,
        note: Optional[str] = None,
    ) -> ApprovalRequest:
        """Deny a pending request."""
        request = await self._store.load(request_id)
        if request is None:
            raise KeyError(f"Approval request not found: {request_id}")
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request is not pending (status={request.status.value})")

        request.status = ApprovalStatus.DENIED
        request.resolved_at = datetime.now(timezone.utc)
        request.resolved_by = approver
        request.resolution_note = note

        await self._store.update(request)

        event = self._pending_events.get(request_id)
        if event:
            event.set()

        logger.info("Denied: %s by %s", request_id, approver)
        return request

    async def cancel(self, request_id: str, reason: str = "") -> ApprovalRequest:
        """Cancel a pending request."""
        request = await self._store.load(request_id)
        if request is None:
            raise KeyError(f"Approval request not found: {request_id}")

        request.status = ApprovalStatus.CANCELLED
        request.resolved_at = datetime.now(timezone.utc)
        request.resolution_note = reason

        await self._store.update(request)

        event = self._pending_events.get(request_id)
        if event:
            event.set()

        return request

    async def check_expired(self) -> List[ApprovalRequest]:
        """Check for expired requests, auto-deny if configured."""
        pending = await self._store.list_by_status(ApprovalStatus.PENDING)
        expired = []

        for req in pending:
            if req.is_expired():
                auto_deny = req.approval_config.auto_deny_on_timeout if req.approval_config else True
                if auto_deny:
                    req.status = ApprovalStatus.EXPIRED
                    req.resolved_at = datetime.now(timezone.utc)
                    req.resolution_note = "Auto-denied: approval timed out"
                    await self._store.update(req)

                    event = self._pending_events.get(req.request_id)
                    if event:
                        event.set()

                expired.append(req)

        return expired

    async def get_pending(self, approver: Optional[str] = None) -> List[ApprovalRequest]:
        """Get pending approval requests."""
        return await self._store.list_pending(approver)

    async def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get a specific approval request."""
        return await self._store.load(request_id)

    async def wait_for_approval(
        self,
        request_id: str,
        timeout: Optional[float] = None,
    ) -> ApprovalRequest:
        """Block until approval is resolved.

        Used by the workflow engine to pause execution at gates.
        """
        event = self._pending_events.get(request_id)
        if event is None:
            # Already resolved — load from store
            request = await self._store.load(request_id)
            if request and request.status != ApprovalStatus.PENDING:
                return request
            # Register event
            event = asyncio.Event()
            self._pending_events[request_id] = event

        effective_timeout = timeout
        if effective_timeout is None:
            request = await self._store.load(request_id)
            if request and request.expires_at:
                remaining = (request.expires_at - datetime.now(timezone.utc)).total_seconds()
                effective_timeout = max(remaining, 0)
            else:
                effective_timeout = 3600

        try:
            await asyncio.wait_for(event.wait(), timeout=effective_timeout)
        except asyncio.TimeoutError:
            await self.check_expired()

        request = await self._store.load(request_id)
        if request is None:
            raise KeyError(f"Approval request lost: {request_id}")
        return request
