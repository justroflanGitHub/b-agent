"""
Base Agent Module

Provides the abstract base class and common data structures for all agents
in the multi-agent coordination system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable
from datetime import datetime
import asyncio
import uuid


class AgentStatus(Enum):
    """Status of an agent."""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"
    INITIALIZING = "initializing"


class AgentCapability(Enum):
    """Capabilities that an agent can have."""
    PLANNING = "planning"
    ANALYSIS = "analysis"
    ACTION_EXECUTION = "action_execution"
    VALIDATION = "validation"
    VISUAL_PROCESSING = "visual_processing"
    FORM_HANDLING = "form_handling"
    DATA_EXTRACTION = "data_extraction"
    NAVIGATION = "navigation"
    RECOVERY = "recovery"
    COORDINATION = "coordination"


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    capabilities: Set[AgentCapability] = field(default_factory=set)
    max_concurrent_tasks: int = 1
    task_timeout: float = 300.0  # 5 minutes
    retry_count: int = 3
    retry_delay: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if agent has a specific capability."""
        return capability in self.capabilities


@dataclass
class AgentResult:
    """Result from an agent task execution."""
    success: bool
    agent_id: str
    task_id: str
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
        }


@dataclass
class AgentState:
    """Current state of an agent."""
    status: AgentStatus = AgentStatus.IDLE
    current_task_id: Optional[str] = None
    last_heartbeat: datetime = field(default_factory=datetime.now)
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_processing_time_ms: float = 0.0
    error_history: List[str] = field(default_factory=list)
    
    def record_task_start(self, task_id: str) -> None:
        """Record the start of a task."""
        self.status = AgentStatus.BUSY
        self.current_task_id = task_id
        self.last_heartbeat = datetime.now()
    
    def record_task_success(self, duration_ms: float) -> None:
        """Record a successful task completion."""
        self.status = AgentStatus.IDLE
        self.current_task_id = None
        self.tasks_completed += 1
        self.total_processing_time_ms += duration_ms
        self.last_heartbeat = datetime.now()
    
    def record_task_failure(self, error: str, duration_ms: float) -> None:
        """Record a failed task."""
        self.status = AgentStatus.IDLE
        self.current_task_id = None
        self.tasks_failed += 1
        self.total_processing_time_ms += duration_ms
        self.error_history.append(error)
        self.last_heartbeat = datetime.now()
        # Keep only last 10 errors
        self.error_history = self.error_history[-10:]


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Provides common functionality for:
    - Status tracking
    - Task execution
    - Error handling
    - Communication
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.state = AgentState()
        self._message_handler: Optional[Callable[[Any], Awaitable[None]]] = None
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    @property
    def agent_id(self) -> str:
        """Get the agent ID."""
        return self.config.agent_id
    
    @property
    def name(self) -> str:
        """Get the agent name."""
        return self.config.name
    
    @property
    def capabilities(self) -> Set[AgentCapability]:
        """Get the agent capabilities."""
        return self.config.capabilities
    
    @property
    def status(self) -> AgentStatus:
        """Get the current agent status."""
        return self.state.status
    
    def has_capability(self, capability: AgentCapability) -> bool:
        """Check if agent has a specific capability."""
        return self.config.has_capability(capability)
    
    def set_message_handler(self, handler: Callable[[Any], Awaitable[None]]) -> None:
        """Set the message handler for incoming messages."""
        self._message_handler = handler
    
    async def send_message(self, message: Any) -> None:
        """Send a message through the message handler."""
        if self._message_handler:
            await self._message_handler(message)
    
    @abstractmethod
    async def execute(self, task: Any) -> AgentResult:
        """
        Execute a task.
        
        Args:
            task: The task to execute
            
        Returns:
            AgentResult with the execution outcome
        """
        pass
    
    async def execute_with_tracking(self, task_id: str, task: Any) -> AgentResult:
        """
        Execute a task with status tracking.
        
        Args:
            task_id: Unique identifier for the task
            task: The task to execute
            
        Returns:
            AgentResult with the execution outcome
        """
        start_time = datetime.now()
        self.state.record_task_start(task_id)
        
        try:
            result = await self.execute(task)
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            result.duration_ms = duration_ms
            
            if result.success:
                self.state.record_task_success(duration_ms)
            else:
                self.state.record_task_failure(result.error or "Unknown error", duration_ms)
            
            return result
            
        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.state.record_task_failure(str(e), duration_ms)
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                task_id=task_id,
                error=str(e),
                duration_ms=duration_ms,
            )
    
    async def start(self) -> None:
        """Start the agent's task processing loop."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
    
    async def stop(self) -> None:
        """Stop the agent's task processing loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
    
    async def _process_loop(self) -> None:
        """Main processing loop for handling queued tasks."""
        while self._running:
            try:
                # Wait for a task with timeout for checking _running
                try:
                    task_id, task = await asyncio.wait_for(
                        self._task_queue.get(),
                        timeout=1.0
                    )
                    await self.execute_with_tracking(task_id, task)
                except asyncio.TimeoutError:
                    continue
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.state.error_history.append(str(e))
    
    async def submit_task(self, task_id: str, task: Any) -> None:
        """Submit a task to the agent's queue."""
        await self._task_queue.put((task_id, task))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "status": self.status.value,
            "capabilities": [c.value for c in self.capabilities],
            "tasks_completed": self.state.tasks_completed,
            "tasks_failed": self.state.tasks_failed,
            "total_processing_time_ms": self.state.total_processing_time_ms,
            "avg_processing_time_ms": (
                self.state.total_processing_time_ms / self.state.tasks_completed
                if self.state.tasks_completed > 0 else 0
            ),
            "error_count": len(self.state.error_history),
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, id={self.agent_id}, status={self.status.value})"
