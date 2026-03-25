"""
Checkpoint System for Browser Agent State Management.

Provides browser state snapshots and restoration capabilities for error recovery.
"""

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


class CheckpointType(Enum):
    """Types of checkpoints."""
    PRE_ACTION = "pre_action"        # Before an action
    POST_ACTION = "post_action"      # After successful action
    TASK_START = "task_start"        # At task beginning
    TASK_END = "task_end"            # At task completion
    MANUAL = "manual"                # Manually created
    RECOVERY = "recovery"            # Before recovery attempt
    BRANCH = "branch"                # Before branching operation


@dataclass
class BrowserState:
    """
    Immutable browser state snapshot.
    
    Captures all necessary information to restore browser state.
    """
    url: str
    title: str
    scroll_x: int = 0
    scroll_y: int = 0
    cookies: List[Dict[str, Any]] = field(default_factory=list)
    local_storage: Dict[str, str] = field(default_factory=dict)
    session_storage: Dict[str, str] = field(default_factory=dict)
    form_values: Dict[str, Any] = field(default_factory=dict)
    screenshot: Optional[bytes] = None
    screenshot_hash: Optional[str] = None
    tab_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Compute screenshot hash if not provided."""
        if self.screenshot and not self.screenshot_hash:
            self.screenshot_hash = hashlib.sha256(self.screenshot).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to dictionary (excludes screenshot bytes)."""
        return {
            "url": self.url,
            "title": self.title,
            "scroll_x": self.scroll_x,
            "scroll_y": self.scroll_y,
            "cookies": self.cookies,
            "local_storage": self.local_storage,
            "session_storage": self.session_storage,
            "form_values": self.form_values,
            "screenshot_hash": self.screenshot_hash,
            "tab_id": self.tab_id,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], screenshot: Optional[bytes] = None) -> "BrowserState":
        """Deserialize state from dictionary."""
        return cls(
            url=data["url"],
            title=data["title"],
            scroll_x=data.get("scroll_x", 0),
            scroll_y=data.get("scroll_y", 0),
            cookies=data.get("cookies", []),
            local_storage=data.get("local_storage", {}),
            session_storage=data.get("session_storage", {}),
            form_values=data.get("form_values", {}),
            screenshot=screenshot,
            screenshot_hash=data.get("screenshot_hash"),
            tab_id=data.get("tab_id"),
            timestamp=data.get("timestamp", time.time()),
        )
    
    def matches(self, other: "BrowserState", ignore_timestamp: bool = True) -> bool:
        """Check if two states are equivalent."""
        if ignore_timestamp:
            return (
                self.url == other.url and
                self.scroll_x == other.scroll_x and
                self.scroll_y == other.scroll_y and
                self.screenshot_hash == other.screenshot_hash
            )
        return self.to_dict() == other.to_dict()


@dataclass
class Checkpoint:
    """
    A checkpoint containing browser state and task context.
    
    Used for state restoration and rollback operations.
    """
    id: str
    state: BrowserState
    checkpoint_type: CheckpointType
    task_step: int = 0
    action_name: Optional[str] = None
    action_result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    parent_id: Optional[str] = None
    children_ids: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize checkpoint to dictionary."""
        return {
            "id": self.id,
            "state": self.state.to_dict(),
            "checkpoint_type": self.checkpoint_type.value,
            "task_step": self.task_step,
            "action_name": self.action_name,
            "action_result": self.action_result,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "parent_id": self.parent_id,
            "children_ids": list(self.children_ids),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], screenshot: Optional[bytes] = None) -> "Checkpoint":
        """Deserialize checkpoint from dictionary."""
        return cls(
            id=data["id"],
            state=BrowserState.from_dict(data["state"], screenshot),
            checkpoint_type=CheckpointType(data["checkpoint_type"]),
            task_step=data.get("task_step", 0),
            action_name=data.get("action_name"),
            action_result=data.get("action_result"),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            parent_id=data.get("parent_id"),
            children_ids=set(data.get("children_ids", [])),
        )


class CheckpointManager:
    """
    Manages browser state checkpoints for recovery and rollback.
    
    Features:
    - Create checkpoints before/after actions
    - Restore browser to previous checkpoint
    - Persist checkpoints to disk
    - Manage checkpoint chain/history
    - Configurable checkpoint interval and limits
    """
    
    def __init__(
        self,
        max_checkpoints: int = 50,
        persist_to_disk: bool = True,
        persistence_dir: Optional[str] = None,
        checkpoint_interval: int = 1,  # Create checkpoint every N actions
        store_screenshots: bool = True,
    ):
        """
        Initialize checkpoint manager.
        
        Args:
            max_checkpoints: Maximum number of checkpoints to keep
            persist_to_disk: Whether to persist checkpoints to disk
            persistence_dir: Directory for checkpoint storage
            checkpoint_interval: Create checkpoint every N actions
            store_screenshots: Whether to store screenshots in checkpoints
        """
        self.max_checkpoints = max_checkpoints
        self.persist_to_disk = persist_to_disk
        self.persistence_dir = Path(persistence_dir or ".checkpoints")
        self.checkpoint_interval = checkpoint_interval
        self.store_screenshots = store_screenshots
        
        # In-memory checkpoint storage
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._checkpoint_order: List[str] = []  # Ordered by creation time
        self._action_counter: int = 0
        self._current_task_checkpoints: List[str] = []  # Checkpoints for current task
        
        # Screenshot storage (separate for efficiency)
        self._screenshots: Dict[str, bytes] = {}
        
        if self.persist_to_disk:
            self._ensure_persistence_dir()
            self._load_from_disk()
    
    def _ensure_persistence_dir(self) -> None:
        """Create persistence directory if needed."""
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
        (self.persistence_dir / "screenshots").mkdir(exist_ok=True)
    
    def _generate_checkpoint_id(self) -> str:
        """Generate unique checkpoint ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"ckpt_{timestamp}_{len(self._checkpoints)}"
    
    def _prune_old_checkpoints(self) -> None:
        """Remove oldest checkpoints if over limit."""
        while len(self._checkpoint_order) > self.max_checkpoints:
            oldest_id = self._checkpoint_order.pop(0)
            if oldest_id in self._checkpoints:
                checkpoint = self._checkpoints.pop(oldest_id)
                # Remove from parent's children
                if checkpoint.parent_id and checkpoint.parent_id in self._checkpoints:
                    self._checkpoints[checkpoint.parent_id].children_ids.discard(oldest_id)
                # Delete screenshot
                if oldest_id in self._screenshots:
                    del self._screenshots[oldest_id]
                # Delete from disk
                if self.persist_to_disk:
                    self._delete_checkpoint_from_disk(oldest_id)
                logger.debug(f"Pruned checkpoint: {oldest_id}")
    
    def _save_checkpoint_to_disk(self, checkpoint: Checkpoint) -> None:
        """Persist checkpoint to disk."""
        if not self.persist_to_disk:
            return
        
        try:
            # Save checkpoint metadata
            checkpoint_file = self.persistence_dir / f"{checkpoint.id}.json"
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
            
            # Save screenshot separately
            if checkpoint.state.screenshot:
                screenshot_file = self.persistence_dir / "screenshots" / f"{checkpoint.id}.png"
                with open(screenshot_file, "wb") as f:
                    f.write(checkpoint.state.screenshot)
            
            logger.debug(f"Saved checkpoint to disk: {checkpoint.id}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint to disk: {e}")
    
    def _delete_checkpoint_from_disk(self, checkpoint_id: str) -> None:
        """Delete checkpoint from disk."""
        if not self.persist_to_disk:
            return
        
        try:
            checkpoint_file = self.persistence_dir / f"{checkpoint_id}.json"
            if checkpoint_file.exists():
                checkpoint_file.unlink()
            
            screenshot_file = self.persistence_dir / "screenshots" / f"{checkpoint_id}.png"
            if screenshot_file.exists():
                screenshot_file.unlink()
            
            logger.debug(f"Deleted checkpoint from disk: {checkpoint_id}")
        except Exception as e:
            logger.error(f"Failed to delete checkpoint from disk: {e}")
    
    def _load_from_disk(self) -> None:
        """Load checkpoints from disk on startup."""
        if not self.persist_to_disk or not self.persistence_dir.exists():
            return
        
        try:
            for checkpoint_file in self.persistence_dir.glob("ckpt_*.json"):
                try:
                    with open(checkpoint_file, "r") as f:
                        data = json.load(f)
                    
                    # Load screenshot if exists
                    screenshot = None
                    screenshot_file = self.persistence_dir / "screenshots" / f"{data['id']}.png"
                    if screenshot_file.exists():
                        with open(screenshot_file, "rb") as f:
                            screenshot = f.read()
                    
                    checkpoint = Checkpoint.from_dict(data, screenshot)
                    self._checkpoints[checkpoint.id] = checkpoint
                    self._checkpoint_order.append(checkpoint.id)
                    
                    if screenshot:
                        self._screenshots[checkpoint.id] = screenshot
                        
                except Exception as e:
                    logger.error(f"Failed to load checkpoint {checkpoint_file}: {e}")
            
            # Sort by creation time
            self._checkpoint_order.sort(
                key=lambda cid: self._checkpoints[cid].created_at
            )
            logger.info(f"Loaded {len(self._checkpoints)} checkpoints from disk")
        except Exception as e:
            logger.error(f"Failed to load checkpoints from disk: {e}")
    
    async def create_checkpoint(
        self,
        page: Any,  # Playwright Page object
        checkpoint_type: CheckpointType = CheckpointType.PRE_ACTION,
        task_step: int = 0,
        action_name: Optional[str] = None,
        action_result: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Checkpoint:
        """
        Create a checkpoint from current browser state.
        
        Args:
            page: Playwright Page object
            checkpoint_type: Type of checkpoint
            task_step: Current step in task
            action_name: Name of action being performed
            action_result: Result of action (for post-action checkpoints)
            metadata: Additional metadata
            
        Returns:
            Created checkpoint
        """
        # Capture browser state
        url = page.url
        title = await page.title()
        
        # Get scroll position
        scroll_position = await page.evaluate("() => ({ x: window.scrollX, y: window.scrollY })")
        scroll_x = scroll_position.get("x", 0)
        scroll_y = scroll_position.get("y", 0)
        
        # Get cookies
        context = page.context
        cookies = await context.cookies()
        
        # Get storage
        local_storage = await page.evaluate("() => Object.assign({}, window.localStorage)")
        session_storage = await page.evaluate("() => Object.assign({}, window.sessionStorage)")
        
        # Get form values
        form_values = await page.evaluate("""
            () => {
                const values = {};
                document.querySelectorAll('input, textarea, select').forEach(el => {
                    const id = el.id || el.name;
                    if (id) {
                        values[id] = el.value;
                    }
                });
                return values;
            }
        """)
        
        # Capture screenshot
        screenshot = None
        if self.store_screenshots:
            screenshot = await page.screenshot(type="png")
        
        # Create browser state
        state = BrowserState(
            url=url,
            title=title,
            scroll_x=scroll_x,
            scroll_y=scroll_y,
            cookies=list(cookies),
            local_storage=dict(local_storage),
            session_storage=dict(session_storage),
            form_values=dict(form_values),
            screenshot=screenshot,
        )
        
        # Create checkpoint
        checkpoint_id = self._generate_checkpoint_id()
        checkpoint = Checkpoint(
            id=checkpoint_id,
            state=state,
            checkpoint_type=checkpoint_type,
            task_step=task_step,
            action_name=action_name,
            action_result=action_result,
            metadata=metadata or {},
        )
        
        # Store checkpoint
        self._checkpoints[checkpoint_id] = checkpoint
        self._checkpoint_order.append(checkpoint_id)
        self._current_task_checkpoints.append(checkpoint_id)
        
        if screenshot:
            self._screenshots[checkpoint_id] = screenshot
        
        # Save to disk
        self._save_checkpoint_to_disk(checkpoint)
        
        # Prune old checkpoints
        self._prune_old_checkpoints()
        
        logger.info(f"Created checkpoint: {checkpoint_id} (type={checkpoint_type.value}, step={task_step})")
        return checkpoint
    
    async def restore_checkpoint(
        self,
        page: Any,
        checkpoint_id: str,
        restore_cookies: bool = True,
        restore_storage: bool = True,
        restore_scroll: bool = True,
        restore_forms: bool = False,
    ) -> bool:
        """
        Restore browser to a checkpoint state.
        
        Args:
            page: Playwright Page object
            checkpoint_id: ID of checkpoint to restore
            restore_cookies: Whether to restore cookies
            restore_storage: Whether to restore storage
            restore_scroll: Whether to restore scroll position
            restore_forms: Whether to restore form values
            
        Returns:
            True if restoration successful
        """
        if checkpoint_id not in self._checkpoints:
            logger.error(f"Checkpoint not found: {checkpoint_id}")
            return False
        
        checkpoint = self._checkpoints[checkpoint_id]
        state = checkpoint.state
        
        try:
            # Navigate to URL
            if page.url != state.url:
                await page.goto(state.url, wait_until="domcontentloaded", timeout=30000)
            
            # Restore cookies
            if restore_cookies and state.cookies:
                context = page.context
                await context.add_cookies(state.cookies)
            
            # Restore storage
            if restore_storage:
                if state.local_storage:
                    await page.evaluate(f"""
                        () => {{
                            const data = {json.dumps(state.local_storage)};
                            Object.entries(data).forEach(([k, v]) => localStorage.setItem(k, v));
                        }}
                    """)
                if state.session_storage:
                    await page.evaluate(f"""
                        () => {{
                            const data = {json.dumps(state.session_storage)};
                            Object.entries(data).forEach(([k, v]) => sessionStorage.setItem(k, v));
                        }}
                    """)
            
            # Restore scroll position
            if restore_scroll:
                await page.evaluate(f"window.scrollTo({state.scroll_x}, {state.scroll_y})")
            
            # Restore form values
            if restore_forms and state.form_values:
                for field_id, value in state.form_values.items():
                    await page.evaluate(f"""
                        () => {{
                            const el = document.getElementById('{field_id}') || 
                                      document.querySelector('[name="{field_id}"]');
                            if (el) el.value = '{value}';
                        }}
                    """)
            
            logger.info(f"Restored checkpoint: {checkpoint_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore checkpoint {checkpoint_id}: {e}")
            return False
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get checkpoint by ID."""
        return self._checkpoints.get(checkpoint_id)
    
    def get_checkpoint_screenshot(self, checkpoint_id: str) -> Optional[bytes]:
        """Get screenshot for a checkpoint."""
        return self._screenshots.get(checkpoint_id)
    
    def get_latest_checkpoint(self, checkpoint_type: Optional[CheckpointType] = None) -> Optional[Checkpoint]:
        """Get most recent checkpoint, optionally filtered by type."""
        if not self._checkpoint_order:
            return None
        
        if checkpoint_type is None:
            return self._checkpoints.get(self._checkpoint_order[-1])
        
        for checkpoint_id in reversed(self._checkpoint_order):
            checkpoint = self._checkpoints.get(checkpoint_id)
            if checkpoint and checkpoint.checkpoint_type == checkpoint_type:
                return checkpoint
        
        return None
    
    def get_checkpoints_by_type(self, checkpoint_type: CheckpointType) -> List[Checkpoint]:
        """Get all checkpoints of a specific type."""
        return [
            self._checkpoints[cid]
            for cid in self._checkpoint_order
            if self._checkpoints[cid].checkpoint_type == checkpoint_type
        ]
    
    def get_checkpoint_chain(self, checkpoint_id: str) -> List[Checkpoint]:
        """Get chain of checkpoints from root to specified checkpoint."""
        chain = []
        current_id = checkpoint_id
        
        while current_id:
            checkpoint = self._checkpoints.get(current_id)
            if not checkpoint:
                break
            chain.insert(0, checkpoint)
            current_id = checkpoint.parent_id
        
        return chain
    
    def get_task_checkpoints(self) -> List[Checkpoint]:
        """Get all checkpoints for current task."""
        return [
            self._checkpoints[cid]
            for cid in self._current_task_checkpoints
            if cid in self._checkpoints
        ]
    
    def clear_task_checkpoints(self) -> None:
        """Clear checkpoints for current task (keep in history)."""
        self._current_task_checkpoints = []
    
    def should_create_checkpoint(self) -> bool:
        """Check if checkpoint should be created based on interval."""
        self._action_counter += 1
        return self._action_counter % self.checkpoint_interval == 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get checkpoint manager statistics."""
        type_counts = {}
        for checkpoint in self._checkpoints.values():
            ctype = checkpoint.checkpoint_type.value
            type_counts[ctype] = type_counts.get(ctype, 0) + 1
        
        total_screenshot_size = sum(len(s) for s in self._screenshots.values())
        
        return {
            "total_checkpoints": len(self._checkpoints),
            "max_checkpoints": self.max_checkpoints,
            "checkpoint_types": type_counts,
            "screenshots_stored": len(self._screenshots),
            "total_screenshot_size_bytes": total_screenshot_size,
            "current_task_checkpoints": len(self._current_task_checkpoints),
            "persistence_enabled": self.persist_to_disk,
            "persistence_dir": str(self.persistence_dir) if self.persist_to_disk else None,
        }
    
    def clear_all(self) -> None:
        """Clear all checkpoints from memory and disk."""
        self._checkpoints.clear()
        self._checkpoint_order.clear()
        self._screenshots.clear()
        self._current_task_checkpoints.clear()
        self._action_counter = 0
        
        if self.persist_to_disk:
            import shutil
            if self.persistence_dir.exists():
                shutil.rmtree(self.persistence_dir)
            self._ensure_persistence_dir()
        
        logger.info("Cleared all checkpoints")
