"""
Browser Agent Task Manager

Manages task lifecycle, queuing, and execution.
"""

import asyncio
import uuid
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import heapq
from collections import defaultdict

from .models import TaskStatusEnum, TaskStatus, TaskResult, ActionResult


logger = logging.getLogger(__name__)


class TaskPriority:
    """Priority queue item wrapper."""
    def __init__(self, priority: int, task_id: str, created_at: float):
        self.priority = priority
        self.task_id = task_id
        self.created_at = created_at
    
    def __lt__(self, other):
        # Higher priority = lower number (processed first)
        if self.priority != other.priority:
            return self.priority > other.priority
        # Earlier created = processed first
        return self.created_at < other.created_at


@dataclass
class Task:
    """Internal task representation."""
    task_id: str
    goal: str
    start_url: Optional[str]
    max_steps: int
    skill: Optional[str]
    config: Dict[str, Any]
    priority: int
    callback_url: Optional[str]
    status: TaskStatusEnum = TaskStatusEnum.PENDING
    progress: float = 0.0
    current_step: int = 0
    total_steps: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    actions: List[ActionResult] = field(default_factory=list)
    extracted_data: Optional[Dict[str, Any]] = None
    final_url: Optional[str] = None
    result: Optional[TaskResult] = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


class TaskManager:
    """
    Manages browser automation tasks.
    
    Features:
    - Task submission with priority
    - Task status tracking
    - Task cancellation
    - Concurrent task execution
    - Metrics collection
    """
    
    def __init__(
        self,
        max_concurrent_tasks: int = 3,
        task_timeout: float = 300.0,
        cleanup_interval: float = 60.0
    ):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_timeout = task_timeout
        self.cleanup_interval = cleanup_interval
        
        # Task storage
        self.tasks: Dict[str, Task] = {}
        self.priority_queue: List[TaskPriority] = []
        
        # Execution tracking
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: List[str] = []
        
        # Metrics
        self.metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_cancelled": 0,
            "total_duration": 0.0,
            "error_types": defaultdict(int),
            "action_latency": defaultdict(list),
            "task_durations": [],
            "success_rates": []
        }
        
        # Callbacks
        self._on_task_complete: Optional[Callable] = None
        self._on_task_start: Optional[Callable] = None
        
        # Control
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._queue_event = asyncio.Event()
    
    def on_task_complete(self, callback: Callable):
        """Register callback for task completion."""
        self._on_task_complete = callback
    
    def on_task_start(self, callback: Callable):
        """Register callback for task start."""
        self._on_task_start = callback
    
    async def start(self):
        """Start the task manager."""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Task manager started")
    
    async def stop(self):
        """Stop the task manager."""
        self._running = False
        self._queue_event.set()
        
        # Cancel active tasks
        for task_id, atask in list(self.active_tasks.items()):
            atask.cancel()
            try:
                await atask
            except asyncio.CancelledError:
                pass
        
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Task manager stopped")
    
    def submit_task(
        self,
        goal: str,
        start_url: Optional[str] = None,
        max_steps: int = 15,
        skill: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        priority: int = 5,
        callback_url: Optional[str] = None
    ) -> str:
        """
        Submit a new task for execution.
        
        Args:
            goal: Natural language goal
            start_url: Starting URL
            max_steps: Maximum steps
            skill: Optional skill name
            config: Task configuration
            priority: Task priority (1-10)
            callback_url: Webhook URL
            
        Returns:
            Task ID
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        
        task = Task(
            task_id=task_id,
            goal=goal,
            start_url=start_url,
            max_steps=max_steps,
            skill=skill,
            config=config or {},
            priority=priority,
            callback_url=callback_url
        )
        
        self.tasks[task_id] = task
        
        # Add to priority queue
        heapq.heappush(
            self.priority_queue,
            TaskPriority(priority, task_id, time.time())
        )
        
        # Signal worker
        self._queue_event.set()
        
        logger.info(f"Task {task_id} submitted with priority {priority}")
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get task status by ID."""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        return TaskStatus(
            task_id=task.task_id,
            status=task.status,
            goal=task.goal,
            progress=task.progress,
            current_step=task.current_step,
            total_steps=task.total_steps,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            error=task.error
        )
    
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get task result by ID."""
        task = self.tasks.get(task_id)
        if not task or not task.result:
            return None
        return task.result
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if cancelled, False if not found or already complete
        """
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status in (TaskStatusEnum.COMPLETED, TaskStatusEnum.FAILED, TaskStatusEnum.CANCELLED):
            return False
        
        # Set cancel event
        task.cancel_event.set()
        task.status = TaskStatusEnum.CANCELLED
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        
        # Cancel asyncio task if active
        if task_id in self.active_tasks:
            self.active_tasks[task_id].cancel()
        
        self.metrics["tasks_cancelled"] += 1
        logger.info(f"Task {task_id} cancelled")
        return True
    
    def list_tasks(
        self,
        status: Optional[TaskStatusEnum] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[TaskStatus]:
        """
        List tasks with optional filtering.
        
        Args:
            status: Filter by status
            limit: Max results
            offset: Offset for pagination
            
        Returns:
            List of task statuses
        """
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # Sort by created_at descending
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return [self.get_task_status(t.task_id) for t in tasks[offset:offset + limit]]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get task manager metrics."""
        total = self.metrics["tasks_completed"] + self.metrics["tasks_failed"]
        avg_duration = (
            self.metrics["total_duration"] / self.metrics["tasks_completed"]
            if self.metrics["tasks_completed"] > 0
            else 0.0
        )
        
        # Calculate average latencies
        avg_latencies = {}
        for action, latencies in self.metrics["action_latency"].items():
            if latencies:
                avg_latencies[action] = sum(latencies) / len(latencies)
        
        return {
            "tasks_completed": self.metrics["tasks_completed"],
            "tasks_failed": self.metrics["tasks_failed"],
            "tasks_cancelled": self.metrics["tasks_cancelled"],
            "average_duration": avg_duration,
            "error_types": dict(self.metrics["error_types"]),
            "action_latency": avg_latencies,
            "active_tasks": len(self.active_tasks),
            "queued_tasks": len(self.priority_queue)
        }
    
    def update_task_progress(
        self,
        task_id: str,
        current_step: int,
        total_steps: int,
        action: Optional[ActionResult] = None
    ):
        """Update task progress."""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        task.current_step = current_step
        task.total_steps = total_steps
        task.progress = current_step / total_steps if total_steps > 0 else 0
        task.updated_at = datetime.utcnow()
        
        if action:
            task.actions.append(action)
    
    def set_task_error(self, task_id: str, error: str, error_type: str = "unknown"):
        """Set task error."""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        task.status = TaskStatusEnum.FAILED
        task.error = error
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        
        self.metrics["tasks_failed"] += 1
        self.metrics["error_types"][error_type] += 1
    
    def complete_task(
        self,
        task_id: str,
        success: bool,
        extracted_data: Optional[Dict[str, Any]] = None,
        final_url: Optional[str] = None
    ):
        """Mark task as complete."""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        task.status = TaskStatusEnum.COMPLETED if success else TaskStatusEnum.FAILED
        task.progress = 1.0
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        task.extracted_data = extracted_data
        task.final_url = final_url
        
        # Create result
        duration = (task.completed_at - task.started_at).total_seconds() if task.started_at else 0
        
        task.result = TaskResult(
            task_id=task.task_id,
            status=task.status,
            goal=task.goal,
            success=success,
            actions=task.actions,
            extracted_data=extracted_data,
            final_url=final_url,
            execution_time=duration,
            created_at=task.created_at,
            completed_at=task.completed_at,
            error=task.error
        )
        
        if success:
            self.metrics["tasks_completed"] += 1
            self.metrics["total_duration"] += duration
            self.metrics["task_durations"].append(duration)
        
        self.completed_tasks.append(task_id)
        
        # Callback
        if self._on_task_complete:
            asyncio.create_task(self._on_task_complete(task))
    
    async def _worker_loop(self):
        """Worker loop for processing tasks."""
        while self._running:
            try:
                # Wait for queue to have items
                await self._queue_event.wait()
                
                # Process queue while we have capacity
                while (
                    len(self.priority_queue) > 0
                    and len(self.active_tasks) < self.max_concurrent_tasks
                ):
                    # Get highest priority task
                    queue_item = heapq.heappop(self.priority_queue)
                    task_id = queue_item.task_id
                    task = self.tasks.get(task_id)
                    
                    if not task or task.status != TaskStatusEnum.PENDING:
                        continue
                    
                    # Start task execution
                    task.status = TaskStatusEnum.RUNNING
                    task.started_at = datetime.utcnow()
                    task.updated_at = datetime.utcnow()
                    
                    # Create execution task
                    atask = asyncio.create_task(self._execute_task(task))
                    self.active_tasks[task_id] = atask
                    
                    # Add completion callback
                    atask.add_done_callback(
                        lambda t, tid=task_id: self._task_done(tid)
                    )
                
                # Clear event if queue is empty
                if len(self.priority_queue) == 0:
                    self._queue_event.clear()
                
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(1)
    
    def _task_done(self, task_id: str):
        """Handle task completion."""
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
    
    async def _execute_task(self, task: Task):
        """
        Execute a single task.
        
        This method should be overridden or a task executor should be set.
        """
        try:
            # Default implementation - just marks as complete
            # Real implementation would call BrowserAgent.execute_task()
            logger.info(f"Executing task {task.task_id}: {task.goal}")
            
            # Simulate some work
            for i in range(task.max_steps):
                if task.cancel_event.is_set():
                    return
                
                task.current_step = i + 1
                task.total_steps = task.max_steps
                task.progress = (i + 1) / task.max_steps
                task.updated_at = datetime.utcnow()
                
                await asyncio.sleep(0.5)
            
            self.complete_task(task.task_id, success=True)
            
        except asyncio.CancelledError:
            task.status = TaskStatusEnum.CANCELLED
            task.completed_at = datetime.utcnow()
        except Exception as e:
            self.set_task_error(task.task_id, str(e), type(e).__name__)
    
    async def _cleanup_loop(self):
        """Cleanup old completed tasks."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                # Remove tasks older than 1 hour
                cutoff = datetime.utcnow().timestamp() - 3600
                to_remove = []
                
                for task_id, task in self.tasks.items():
                    if task.completed_at and task.completed_at.timestamp() < cutoff:
                        if task_id not in self.active_tasks:
                            to_remove.append(task_id)
                
                for task_id in to_remove:
                    del self.tasks[task_id]
                    if task_id in self.completed_tasks:
                        self.completed_tasks.remove(task_id)
                
                if to_remove:
                    logger.info(f"Cleaned up {len(to_remove)} old tasks")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
