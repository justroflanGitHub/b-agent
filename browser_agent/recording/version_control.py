"""Recording version control — diff, rollback, and version management."""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from .recorder import Recording, RecordingStore

logger = logging.getLogger(__name__)


@dataclass
class RecordingDiff:
    """Difference between two recording versions."""

    version_a: int = 0
    version_b: int = 0
    actions_added: List[int] = field(default_factory=list)
    actions_removed: List[int] = field(default_factory=list)
    actions_modified: List[int] = field(default_factory=list)
    selectors_changed: List[int] = field(default_factory=list)
    parameters_added: List[str] = field(default_factory=list)
    parameters_removed: List[str] = field(default_factory=list)
    parameters_modified: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "version_a": self.version_a,
            "version_b": self.version_b,
            "actions_added": self.actions_added,
            "actions_removed": self.actions_removed,
            "actions_modified": self.actions_modified,
            "selectors_changed": self.selectors_changed,
            "parameters_added": self.parameters_added,
            "parameters_removed": self.parameters_removed,
            "parameters_modified": self.parameters_modified,
            "summary": self.summary,
        }


class RecordingVersionControl:
    """Version control for recordings.

    Save versions, diff between versions, and rollback.
    """

    def __init__(self, store: Optional[RecordingStore] = None):
        self._store = store or RecordingStore()

    async def save_version(
        self,
        recording: Recording,
        change_description: Optional[str] = None,
    ) -> Recording:
        """Save a new version of a recording."""
        recording.version += 1
        recording.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        recording.change_description = change_description
        await self._store.save(recording)
        logger.info("Saved recording %s v%d: %s", recording.recording_id[:8], recording.version, change_description)
        return recording

    async def get_version(self, recording_id: str, version: int) -> Optional[Recording]:
        """Get a specific version."""
        return await self._store.load(recording_id, version)

    async def get_latest(self, recording_id: str) -> Optional[Recording]:
        """Get latest version."""
        return await self._store.load(recording_id)

    async def list_versions(self, recording_id: str) -> List[dict]:
        """List all versions."""
        return await self._store.list_versions(recording_id)

    async def diff(
        self,
        recording_id: str,
        version_a: int,
        version_b: int,
    ) -> RecordingDiff:
        """Compare two versions."""
        rec_a = await self._store.load(recording_id, version_a)
        rec_b = await self._store.load(recording_id, version_b)

        if rec_a is None or rec_b is None:
            return RecordingDiff(version_a=version_a, version_b=version_b, summary="Version not found")

        result = RecordingDiff(version_a=version_a, version_b=version_b)

        # Compare actions by step_index
        actions_a = {a.step_index: a for a in rec_a.actions}
        actions_b = {a.step_index: a for a in rec_b.actions}

        for idx in set(actions_a.keys()) | set(actions_b.keys()):
            if idx not in actions_a:
                result.actions_added.append(idx)
            elif idx not in actions_b:
                result.actions_removed.append(idx)
            else:
                a, b = actions_a[idx], actions_b[idx]
                if a.action_type != b.action_type or a.parameters != b.parameters:
                    result.actions_modified.append(idx)
                if a.target_selector != b.target_selector:
                    result.selectors_changed.append(idx)

        # Compare parameters
        params_a = {p.name: p for p in rec_a.parameters}
        params_b = {p.name: p for p in rec_b.parameters}

        for name in set(params_a.keys()) | set(params_b.keys()):
            if name not in params_a:
                result.parameters_added.append(name)
            elif name not in params_b:
                result.parameters_removed.append(name)
            elif params_a[name].default_value != params_b[name].default_value:
                result.parameters_modified.append(name)

        # Summary
        changes = []
        if result.actions_added:
            changes.append(f"+{len(result.actions_added)} actions")
        if result.actions_removed:
            changes.append(f"-{len(result.actions_removed)} actions")
        if result.actions_modified:
            changes.append(f"~{len(result.actions_modified)} modified")
        if result.selectors_changed:
            changes.append(f"{len(result.selectors_changed)} selector changes")
        result.summary = ", ".join(changes) if changes else "No changes"

        return result

    async def rollback(self, recording_id: str, target_version: int) -> Optional[Recording]:
        """Rollback to a previous version (creates new version with old content)."""
        old = await self._store.load(recording_id, target_version)
        if old is None:
            return None

        latest = await self._store.load(recording_id)
        if latest is None:
            return None

        # Create new version with old actions
        latest.actions = old.actions
        latest.parameters = old.parameters
        latest.start_url = old.start_url
        latest.end_url = old.end_url
        latest.parent_version = target_version
        latest.change_description = f"Rollback to v{target_version}"

        return await self.save_version(latest, f"Rollback to v{target_version}")
