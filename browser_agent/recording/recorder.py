"""Workflow recorder — capture browser actions step by step.

Records each action with screenshots, element context, and result,
then stores the recording for later replay.
"""

import hashlib
import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RecordedAction:
    """A single recorded action."""
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    step_index: int = 0
    action_type: str = ""                         # click, type_text, navigate, etc.
    target_url: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Visual context
    screenshot_before_hash: Optional[str] = None
    screenshot_after_hash: Optional[str] = None

    # Element context
    target_selector: Optional[str] = None
    target_coordinates: Optional[Tuple[int, int]] = None
    target_description: Optional[str] = None
    target_text: Optional[str] = None
    target_element_type: Optional[str] = None

    # Page context
    page_title: Optional[str] = None
    page_url: Optional[str] = None
    page_state_hash: Optional[str] = None

    # Result
    success: bool = True
    result_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # Parameterization
    is_parameterized: bool = False
    parameter_name: Optional[str] = None
    parameter_type: Optional[str] = None
    original_value: Optional[Any] = None

    timestamp: float = 0.0

    def to_dict(self) -> dict:
        d = {
            "action_id": self.action_id,
            "step_index": self.step_index,
            "action_type": self.action_type,
            "target_url": self.target_url,
            "parameters": self.parameters,
            "target_selector": self.target_selector,
            "target_coordinates": list(self.target_coordinates) if self.target_coordinates else None,
            "target_description": self.target_description,
            "target_text": self.target_text,
            "target_element_type": self.target_element_type,
            "page_title": self.page_title,
            "page_url": self.page_url,
            "page_state_hash": self.page_state_hash,
            "success": self.success,
            "error": self.error,
            "is_parameterized": self.is_parameterized,
            "parameter_name": self.parameter_name,
            "parameter_type": self.parameter_type,
            "original_value": self.original_value,
            "timestamp": self.timestamp,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "RecordedAction":
        coords = data.get("target_coordinates")
        return cls(
            action_id=data.get("action_id", str(uuid.uuid4())),
            step_index=data.get("step_index", 0),
            action_type=data.get("action_type", ""),
            target_url=data.get("target_url", ""),
            parameters=data.get("parameters", {}),
            target_selector=data.get("target_selector"),
            target_coordinates=tuple(coords) if coords else None,
            target_description=data.get("target_description"),
            target_text=data.get("target_text"),
            target_element_type=data.get("target_element_type"),
            page_title=data.get("page_title"),
            page_url=data.get("page_url"),
            page_state_hash=data.get("page_state_hash"),
            success=data.get("success", True),
            error=data.get("error"),
            is_parameterized=data.get("is_parameterized", False),
            parameter_name=data.get("parameter_name"),
            parameter_type=data.get("parameter_type"),
            original_value=data.get("original_value"),
            timestamp=data.get("timestamp", 0.0),
        )


@dataclass
class RecordingParameter:
    """A parameterized value in a recording."""
    name: str = ""
    display_name: str = ""
    parameter_type: str = "text"       # text, url, select, date, email
    default_value: Any = None
    required: bool = True
    description: Optional[str] = None
    validation_pattern: Optional[str] = None
    options: Optional[List[str]] = None
    field_index: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "parameter_type": self.parameter_type,
            "default_value": self.default_value,
            "required": self.required,
            "description": self.description,
            "validation_pattern": self.validation_pattern,
            "options": self.options,
            "field_index": self.field_index,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecordingParameter":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Recording:
    """A recorded workflow."""
    recording_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    tenant_id: str = "default"
    created_by: str = "system"

    # Recording data
    actions: List[RecordedAction] = field(default_factory=list)
    total_steps: int = 0
    start_url: str = ""
    end_url: Optional[str] = None

    # Parameters
    parameters: List[RecordingParameter] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    tags: List[str] = field(default_factory=list)

    # Execution stats
    run_count: int = 0
    success_count: int = 0
    avg_duration: float = 0.0
    last_run: Optional[datetime] = None

    # Versioning
    parent_version: Optional[int] = None
    change_description: Optional[str] = None

    @property
    def steps(self) -> List[RecordedAction]:
        """Alias for actions."""
        return self.actions

    def __post_init__(self):
        if self.total_steps == 0 and self.actions:
            self.total_steps = len(self.actions)

    def to_dict(self) -> dict:
        return {
            "recording_id": self.recording_id,
            "name": self.name,
            "description": self.description,
            "tenant_id": self.tenant_id,
            "created_by": self.created_by,
            "actions": [a.to_dict() for a in self.actions],
            "total_steps": len(self.actions),
            "start_url": self.start_url,
            "end_url": self.end_url,
            "parameters": [p.to_dict() for p in self.parameters],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "tags": self.tags,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "avg_duration": self.avg_duration,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "parent_version": self.parent_version,
            "change_description": self.change_description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Recording":
        return cls(
            recording_id=data.get("recording_id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            tenant_id=data.get("tenant_id", "default"),
            created_by=data.get("created_by", "system"),
            actions=[RecordedAction.from_dict(a) for a in data.get("actions", [])],
            start_url=data.get("start_url", ""),
            end_url=data.get("end_url"),
            parameters=[RecordingParameter.from_dict(p) for p in data.get("parameters", [])],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(timezone.utc),
            version=data.get("version", 1),
            tags=data.get("tags", []),
            run_count=data.get("run_count", 0),
            success_count=data.get("success_count", 0),
            avg_duration=data.get("avg_duration", 0.0),
            last_run=datetime.fromisoformat(data["last_run"]) if data.get("last_run") else None,
            parent_version=data.get("parent_version"),
            change_description=data.get("change_description"),
        )

    def compute_hash(self) -> str:
        """Hash of all action types + targets for change detection."""
        payload = json.dumps(
            [{"type": a.action_type, "url": a.target_url, "selector": a.target_selector}
             for a in self.actions],
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


class RecordingStore:
    """SQLite storage for recordings."""

    def __init__(self, path: str = ".recordings/recordings.db"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._path = path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self._path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recordings (
                recording_id TEXT,
                version INTEGER DEFAULT 1,
                tenant_id TEXT DEFAULT 'default',
                name TEXT DEFAULT '',
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_latest INTEGER DEFAULT 1,
                PRIMARY KEY (recording_id, version)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rec_tenant ON recordings(tenant_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rec_latest ON recordings(recording_id, is_latest)")
        conn.commit()
        conn.close()

    async def save(self, recording: Recording) -> str:
        conn = sqlite3.connect(self._path)
        # Mark previous versions as not latest
        conn.execute(
            "UPDATE recordings SET is_latest=0 WHERE recording_id=?",
            (recording.recording_id,),
        )
        conn.execute(
            "INSERT INTO recordings VALUES (?,?,?,?,?,?,?,?)",
            (
                recording.recording_id,
                recording.version,
                recording.tenant_id,
                recording.name,
                json.dumps(recording.to_dict()),
                recording.created_at.isoformat(),
                recording.updated_at.isoformat(),
                1,
            ),
        )
        conn.commit()
        conn.close()
        return recording.recording_id

    async def load(self, recording_id: str, version: Optional[int] = None) -> Optional[Recording]:
        conn = sqlite3.connect(self._path)
        if version:
            cursor = conn.execute(
                "SELECT data FROM recordings WHERE recording_id=? AND version=?",
                (recording_id, version),
            )
        else:
            cursor = conn.execute(
                "SELECT data FROM recordings WHERE recording_id=? AND is_latest=1",
                (recording_id,),
            )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return Recording.from_dict(json.loads(row[0]))

    async def list_recordings(self, tenant_id: str) -> List[Recording]:
        conn = sqlite3.connect(self._path)
        cursor = conn.execute(
            "SELECT data FROM recordings WHERE tenant_id=? AND is_latest=1 ORDER BY updated_at DESC",
            (tenant_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [Recording.from_dict(json.loads(r[0])) for r in rows]

    async def list_versions(self, recording_id: str) -> List[dict]:
        conn = sqlite3.connect(self._path)
        cursor = conn.execute(
            "SELECT version, name, created_at FROM recordings WHERE recording_id=? ORDER BY version DESC",
            (recording_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [{"version": r[0], "change_description": r[1], "created_at": r[2]} for r in rows]

    async def delete(self, recording_id: str) -> bool:
        conn = sqlite3.connect(self._path)
        cursor = conn.execute("DELETE FROM recordings WHERE recording_id=?", (recording_id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0


class WorkflowRecorder:
    """Record browser workflows step by step."""

    def __init__(self, store: Optional[RecordingStore] = None):
        self._store = store or RecordingStore()
        self._current: Optional[Recording] = None
        self._paused = False

    async def start_recording(
        self,
        name: str,
        start_url: str = "",
        description: str = "",
        tenant_id: str = "default",
        created_by: str = "system",
        tags: Optional[List[str]] = None,
    ) -> Recording:
        """Start recording a new workflow."""
        self._current = Recording(
            name=name,
            description=description,
            tenant_id=tenant_id,
            created_by=created_by,
            start_url=start_url,
            tags=tags or [],
        )
        self._paused = False
        logger.info("Recording started: %s (%s)", name, self._current.recording_id)
        return self._current

    async def record_action(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        target_url: str = "",
        target_selector: Optional[str] = None,
        target_coordinates: Optional[Tuple[int, int]] = None,
        target_description: Optional[str] = None,
        target_text: Optional[str] = None,
        target_element_type: Optional[str] = None,
        page_title: Optional[str] = None,
        page_url: Optional[str] = None,
        page_state_hash: Optional[str] = None,
        success: bool = True,
        result_data: Optional[Dict] = None,
        error: Optional[str] = None,
    ) -> Optional[RecordedAction]:
        """Record a single action."""
        if self._current is None or self._paused:
            return None

        import time
        action = RecordedAction(
            step_index=len(self._current.actions),
            action_type=action_type,
            target_url=target_url,
            parameters=parameters,
            target_selector=target_selector,
            target_coordinates=target_coordinates,
            target_description=target_description,
            target_text=target_text,
            target_element_type=target_element_type,
            page_title=page_title,
            page_url=page_url,
            page_state_hash=page_state_hash,
            success=success,
            result_data=result_data,
            error=error,
            timestamp=time.time(),
        )

        self._current.actions.append(action)
        self._current.end_url = page_url or target_url
        return action

    async def stop_recording(self) -> Optional[Recording]:
        """Stop recording and persist."""
        if self._current is None:
            return None

        self._current.total_steps = len(self._current.actions)
        self._current.updated_at = datetime.now(timezone.utc)
        await self._store.save(self._current)

        logger.info("Recording stopped: %s (%d steps)", self._current.name, self._current.total_steps)
        recording = self._current
        self._current = None
        return recording

    async def pause_recording(self):
        self._paused = True

    async def resume_recording(self):
        self._paused = False

    @property
    def is_recording(self) -> bool:
        return self._current is not None and not self._paused

    @property
    def current(self) -> Optional[Recording]:
        return self._current
