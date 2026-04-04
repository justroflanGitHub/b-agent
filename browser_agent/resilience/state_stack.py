"""
State Stack for Browser Agent Rollback Operations.

Provides stack-based state management for multi-level rollback.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
import logging

from .checkpoint import BrowserState

logger = logging.getLogger(__name__)


@dataclass
class StateFrame:
    """
    A frame in the state stack representing a point-in-time state.

    Supports branching for exploration scenarios.
    """

    id: str
    state: BrowserState
    step_index: int = 0
    action_name: Optional[str] = None
    action_description: Optional[str] = None
    parent_id: Optional[str] = None
    children_ids: Set[str] = field(default_factory=set)
    is_branch_point: bool = False
    branch_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0

    def touch(self) -> None:
        """Update access time and count."""
        self.accessed_at = datetime.now()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize frame to dictionary."""
        return {
            "id": self.id,
            "state": self.state.to_dict(),
            "step_index": self.step_index,
            "action_name": self.action_name,
            "action_description": self.action_description,
            "parent_id": self.parent_id,
            "children_ids": list(self.children_ids),
            "is_branch_point": self.is_branch_point,
            "branch_name": self.branch_name,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
        }


class StateStack:
    """
    Stack-based state management for rollback operations.

    Features:
    - Push/pop state operations
    - Multi-level rollback
    - Branch point creation for exploration
    - Branch merging
    - Max depth enforcement
    - Orphan frame pruning
    """

    def __init__(
        self,
        max_depth: int = 20,
        auto_prune: bool = True,
        prune_threshold: float = 0.8,  # Prune when at 80% capacity
    ):
        """
        Initialize state stack.

        Args:
            max_depth: Maximum stack depth
            auto_prune: Whether to automatically prune old frames
            prune_threshold: Threshold for auto-pruning (0-1)
        """
        self.max_depth = max_depth
        self.auto_prune = auto_prune
        self.prune_threshold = prune_threshold

        # Stack storage
        self._frames: Dict[str, StateFrame] = {}
        self._stack: List[str] = []  # Ordered stack of frame IDs
        self._current_frame_id: Optional[str] = None

        # Branch tracking
        self._branches: Dict[str, List[str]] = {}  # branch_name -> frame IDs
        self._current_branch: Optional[str] = None

        # Counters
        self._frame_counter: int = 0
        self._push_count: int = 0
        self._pop_count: int = 0
        self._rollback_count: int = 0

    def _generate_frame_id(self) -> str:
        """Generate unique frame ID."""
        self._frame_counter += 1
        timestamp = datetime.now().strftime("%H%M%S")
        return f"frame_{timestamp}_{self._frame_counter}"

    def _prune_if_needed(self) -> None:
        """Prune old frames if over threshold."""
        if not self.auto_prune:
            return

        threshold_count = int(self.max_depth * self.prune_threshold)
        if len(self._stack) <= threshold_count:
            return

        # Calculate how many to remove
        prune_count = len(self._stack) - int(self.max_depth * 0.6)

        # Don't prune branch points
        pruned = 0
        while pruned < prune_count and len(self._stack) > 1:
            frame_id = self._stack[0]
            frame = self._frames.get(frame_id)

            if frame and frame.is_branch_point:
                # Skip branch points, they're important
                break

            # Remove frame
            self._stack.pop(0)
            if frame_id in self._frames:
                del self._frames[frame_id]

            # Update parent's children
            if frame and frame.parent_id and frame.parent_id in self._frames:
                self._frames[frame.parent_id].children_ids.discard(frame_id)

            pruned += 1

        if pruned > 0:
            logger.debug(f"Pruned {pruned} frames from state stack")

    def push(
        self,
        state: BrowserState,
        action_name: Optional[str] = None,
        action_description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_branch_point: bool = False,
        branch_name: Optional[str] = None,
    ) -> StateFrame:
        """
        Push a new state onto the stack.

        Args:
            state: Browser state to push
            action_name: Name of action that led to this state
            action_description: Human-readable description
            metadata: Additional metadata
            is_branch_point: Whether this is a branch point
            branch_name: Name for this branch

        Returns:
            Created state frame
        """
        # Create frame
        frame_id = self._generate_frame_id()
        frame = StateFrame(
            id=frame_id,
            state=state,
            step_index=len(self._stack),
            action_name=action_name,
            action_description=action_description,
            parent_id=self._current_frame_id,
            is_branch_point=is_branch_point,
            branch_name=branch_name,
            metadata=metadata or {},
        )

        # Update parent's children
        if self._current_frame_id and self._current_frame_id in self._frames:
            self._frames[self._current_frame_id].children_ids.add(frame_id)

        # Store frame
        self._frames[frame_id] = frame
        self._stack.append(frame_id)
        self._current_frame_id = frame_id

        # Track branch
        if branch_name:
            if branch_name not in self._branches:
                self._branches[branch_name] = []
            self._branches[branch_name].append(frame_id)
            self._current_branch = branch_name

        self._push_count += 1

        # Prune if needed
        self._prune_if_needed()

        logger.debug(f"Pushed frame: {frame_id} (depth={len(self._stack)})")
        return frame

    def pop(self) -> Optional[StateFrame]:
        """
        Pop the top state from the stack.

        Returns:
            Popped frame, or None if stack is empty
        """
        if not self._stack:
            return None

        frame_id = self._stack.pop()
        frame = self._frames.get(frame_id)

        if frame:
            # Update parent's children
            if frame.parent_id and frame.parent_id in self._frames:
                self._frames[frame.parent_id].children_ids.discard(frame_id)

            # Update current frame
            if self._stack:
                self._current_frame_id = self._stack[-1]
            else:
                self._current_frame_id = None

            # Remove from frames dict
            del self._frames[frame_id]

            self._pop_count += 1
            logger.debug(f"Popped frame: {frame_id} (depth={len(self._stack)})")

        return frame

    def peek(self, depth: int = 0) -> Optional[StateFrame]:
        """
        Peek at a frame without removing it.

        Args:
            depth: Depth from top (0 = top)

        Returns:
            Frame at depth, or None if not found
        """
        if depth < 0 or depth >= len(self._stack):
            return None

        frame_id = self._stack[-(depth + 1)]
        frame = self._frames.get(frame_id)

        if frame:
            frame.touch()

        return frame

    def rollback(self, steps: int = 1) -> Optional[StateFrame]:
        """
        Rollback by specified number of steps.

        Args:
            steps: Number of steps to rollback

        Returns:
            Frame after rollback, or None if not possible
        """
        if steps <= 0 or steps > len(self._stack):
            logger.warning(f"Invalid rollback steps: {steps} (stack depth: {len(self._stack)})")
            return None

        # Find target frame
        target_idx = len(self._stack) - steps - 1
        if target_idx < 0:
            target_idx = 0

        target_frame_id = self._stack[target_idx]

        # Pop frames until we reach target
        popped_count = 0
        while len(self._stack) > target_idx + 1:
            frame_id = self._stack.pop()
            if frame_id in self._frames:
                frame = self._frames[frame_id]
                # Update parent's children
                if frame.parent_id and frame.parent_id in self._frames:
                    self._frames[frame.parent_id].children_ids.discard(frame_id)
                del self._frames[frame_id]
            popped_count += 1

        self._current_frame_id = target_frame_id if self._stack else None
        self._rollback_count += 1

        result = self._frames.get(target_frame_id)
        if result:
            result.touch()

        logger.info(f"Rolled back {popped_count} steps to frame: {target_frame_id}")
        return result

    def rollback_to_frame(self, frame_id: str) -> Optional[StateFrame]:
        """
        Rollback to a specific frame.

        Args:
            frame_id: ID of frame to rollback to

        Returns:
            Target frame, or None if not found
        """
        if frame_id not in self._frames:
            logger.warning(f"Frame not found for rollback: {frame_id}")
            return None

        try:
            target_idx = self._stack.index(frame_id)
        except ValueError:
            logger.warning(f"Frame not in stack: {frame_id}")
            return None

        # Pop frames until we reach target
        popped_count = 0
        while len(self._stack) > target_idx + 1:
            frame_id_to_pop = self._stack.pop()
            if frame_id_to_pop in self._frames:
                frame = self._frames[frame_id_to_pop]
                if frame.parent_id and frame.parent_id in self._frames:
                    self._frames[frame.parent_id].children_ids.discard(frame_id_to_pop)
                del self._frames[frame_id_to_pop]
            popped_count += 1

        self._current_frame_id = frame_id
        self._rollback_count += 1

        result = self._frames.get(frame_id)
        if result:
            result.touch()

        logger.info(f"Rolled back to frame: {frame_id} (popped {popped_count} frames)")
        return result

    def create_branch(
        self,
        branch_name: str,
        state: Optional[BrowserState] = None,
    ) -> StateFrame:
        """
        Create a new branch from current position.

        Args:
            branch_name: Name for the new branch
            state: State for branch point (uses current if not provided)

        Returns:
            Branch point frame
        """
        # Get current state if not provided
        if state is None:
            current = self.peek()
            if current is None:
                raise ValueError("No current state to branch from")
            state = current.state

        # Create branch point
        branch_frame = self.push(
            state=state,
            action_name="branch",
            action_description=f"Created branch: {branch_name}",
            is_branch_point=True,
            branch_name=branch_name,
        )

        logger.info(f"Created branch: {branch_name} at frame: {branch_frame.id}")
        return branch_frame

    def switch_branch(self, branch_name: str) -> Optional[StateFrame]:
        """
        Switch to a different branch.

        Args:
            branch_name: Name of branch to switch to

        Returns:
            Latest frame in branch, or None if not found
        """
        if branch_name not in self._branches or not self._branches[branch_name]:
            logger.warning(f"Branch not found: {branch_name}")
            return None

        # Get latest frame in branch
        frame_id = self._branches[branch_name][-1]
        if frame_id not in self._frames:
            logger.warning(f"Branch frame not found: {frame_id}")
            return None

        self._current_branch = branch_name
        frame = self._frames[frame_id]
        frame.touch()

        logger.info(f"Switched to branch: {branch_name}")
        return frame

    def merge_branch(
        self,
        source_branch: str,
        target_branch: Optional[str] = None,
    ) -> bool:
        """
        Merge a source branch into target branch.

        Args:
            source_branch: Name of branch to merge from
            target_branch: Name of branch to merge into (current if None)

        Returns:
            True if merge successful
        """
        if source_branch not in self._branches:
            logger.warning(f"Source branch not found: {source_branch}")
            return False

        if target_branch and target_branch not in self._branches:
            logger.warning(f"Target branch not found: {target_branch}")
            return False

        # For now, just switch to the merged state
        # A real implementation would reconcile the states
        source_frames = self._branches[source_branch]
        if source_frames:
            self._current_branch = target_branch or self._current_branch
            logger.info(f"Merged branch {source_branch} into {target_branch or 'current'}")
            return True

        return False

    def get_frame(self, frame_id: str) -> Optional[StateFrame]:
        """Get frame by ID."""
        frame = self._frames.get(frame_id)
        if frame:
            frame.touch()
        return frame

    def get_current_frame(self) -> Optional[StateFrame]:
        """Get current (top) frame."""
        return self.peek(0)

    def get_frame_history(self, limit: int = 10) -> List[StateFrame]:
        """Get recent frame history."""
        frames = []
        for frame_id in reversed(self._stack[-limit:]):
            if frame_id in self._frames:
                frames.append(self._frames[frame_id])
        return frames

    def get_branch_frames(self, branch_name: str) -> List[StateFrame]:
        """Get all frames in a branch."""
        frames = []
        for frame_id in self._branches.get(branch_name, []):
            if frame_id in self._frames:
                frames.append(self._frames[frame_id])
        return frames

    def get_all_branches(self) -> Dict[str, int]:
        """Get all branches with their frame counts."""
        return {name: len(frames) for name, frames in self._branches.items()}

    def get_depth(self) -> int:
        """Get current stack depth."""
        return len(self._stack)

    def is_empty(self) -> bool:
        """Check if stack is empty."""
        return len(self._stack) == 0

    def clear(self) -> None:
        """Clear all frames from stack."""
        self._frames.clear()
        self._stack.clear()
        self._branches.clear()
        self._current_frame_id = None
        self._current_branch = None
        logger.info("Cleared state stack")

    def get_statistics(self) -> Dict[str, Any]:
        """Get stack statistics."""
        branch_point_count = sum(1 for f in self._frames.values() if f.is_branch_point)

        return {
            "depth": len(self._stack),
            "max_depth": self.max_depth,
            "total_frames": len(self._frames),
            "branch_count": len(self._branches),
            "branch_point_count": branch_point_count,
            "current_branch": self._current_branch,
            "push_count": self._push_count,
            "pop_count": self._pop_count,
            "rollback_count": self._rollback_count,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize stack to dictionary."""
        return {
            "frames": {fid: f.to_dict() for fid, f in self._frames.items()},
            "stack": self._stack,
            "current_frame_id": self._current_frame_id,
            "branches": self._branches,
            "current_branch": self._current_branch,
        }
