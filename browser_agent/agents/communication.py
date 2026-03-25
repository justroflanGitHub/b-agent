"""
Agent Communication Module

Provides the message passing system for inter-agent communication.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable
from datetime import datetime
import asyncio
import uuid
from collections import defaultdict


class MessageType(Enum):
    """Types of messages between agents."""
    # Task-related
    TASK_ASSIGNMENT = "task_assignment"
    TASK_RESULT = "task_result"
    TASK_STATUS = "task_status"
    TASK_CANCEL = "task_cancel"
    
    # Coordination
    STATUS_UPDATE = "status_update"
    HEARTBEAT = "heartbeat"
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"
    
    # Data sharing
    DATA_SHARE = "data_share"
    QUERY = "query"
    QUERY_RESPONSE = "query_response"
    
    # Control
    REGISTER = "register"
    UNREGISTER = "unregister"
    CONFIG_UPDATE = "config_update"
    
    # Error handling
    ERROR = "error"
    WARNING = "warning"
    
    # Collaboration
    HELP_REQUEST = "help_request"
    HELP_RESPONSE = "help_response"
    DELEGATION = "delegation"
    DELEGATION_RESULT = "delegation_result"


class MessagePriority(Enum):
    """Priority levels for messages."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class AgentMessage:
    """A message sent between agents."""
    message_type: MessageType
    sender_id: str
    receiver_id: Optional[str] = None  # None for broadcast
    payload: Any = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None  # For request-response correlation
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if the message has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def is_broadcast(self) -> bool:
        """Check if this is a broadcast message."""
        return self.receiver_id is None
    
    def create_response(
        self,
        message_type: MessageType,
        payload: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> "AgentMessage":
        """Create a response message."""
        return AgentMessage(
            message_type=message_type,
            sender_id=self.receiver_id or "",
            receiver_id=self.sender_id,
            payload=payload,
            correlation_id=self.message_id,
            priority=priority,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create from dictionary."""
        return cls(
            message_id=data["message_id"],
            message_type=MessageType(data["message_type"]),
            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],
            payload=data["payload"],
            correlation_id=data["correlation_id"],
            priority=MessagePriority(data["priority"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
        )


class AgentCommunicationBus:
    """
    Communication bus for inter-agent messaging.
    
    Provides:
    - Point-to-point messaging
    - Broadcast messaging
    - Message queuing
    - Subscription-based routing
    - Message history
    """
    
    def __init__(
        self,
        max_queue_size: int = 1000,
        history_size: int = 100,
        enable_history: bool = True,
    ):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._handlers: Dict[str, Callable[[AgentMessage], Awaitable[None]]] = {}
        self._subscriptions: Dict[str, List[str]] = defaultdict(list)  # topic -> agent_ids
        self._history: List[AgentMessage] = []
        self._max_queue_size = max_queue_size
        self._history_size = history_size
        self._enable_history = enable_history
        self._lock = asyncio.Lock()
    
    async def register_agent(
        self,
        agent_id: str,
        handler: Optional[Callable[[AgentMessage], Awaitable[None]]] = None,
    ) -> None:
        """Register an agent with the communication bus."""
        async with self._lock:
            if agent_id not in self._queues:
                self._queues[agent_id] = asyncio.Queue(maxsize=self._max_queue_size)
            if handler:
                self._handlers[agent_id] = handler
    
    async def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from the communication bus."""
        async with self._lock:
            self._queues.pop(agent_id, None)
            self._handlers.pop(agent_id, None)
            # Remove from all subscriptions
            for topic in self._subscriptions:
                if agent_id in self._subscriptions[topic]:
                    self._subscriptions[topic].remove(agent_id)
    
    async def subscribe(self, agent_id: str, topic: str) -> None:
        """Subscribe an agent to a topic."""
        async with self._lock:
            if agent_id not in self._subscriptions[topic]:
                self._subscriptions[topic].append(agent_id)
    
    async def unsubscribe(self, agent_id: str, topic: str) -> None:
        """Unsubscribe an agent from a topic."""
        async with self._lock:
            if agent_id in self._subscriptions[topic]:
                self._subscriptions[topic].remove(agent_id)
    
    async def send(self, message: AgentMessage) -> bool:
        """
        Send a message.
        
        If receiver_id is set, sends directly to that agent.
        If receiver_id is None, broadcasts to all agents.
        
        Returns True if message was queued successfully.
        """
        if message.is_expired():
            return False
        
        # Add to history
        if self._enable_history:
            self._history.append(message)
            if len(self._history) > self._history_size:
                self._history = self._history[-self._history_size:]
        
        if message.is_broadcast():
            # Broadcast to all registered agents
            for agent_id, queue in self._queues.items():
                if agent_id != message.sender_id:  # Don't send to self
                    try:
                        queue.put_nowait(message)
                        # Trigger handler if registered
                        if agent_id in self._handlers:
                            asyncio.create_task(self._handlers[agent_id](message))
                    except asyncio.QueueFull:
                        pass  # Queue full, skip
            return True
        else:
            # Point-to-point message
            if message.receiver_id in self._queues:
                try:
                    await self._queues[message.receiver_id].put(message)
                    # Trigger handler if registered
                    if message.receiver_id in self._handlers:
                        asyncio.create_task(self._handlers[message.receiver_id](message))
                    return True
                except asyncio.QueueFull:
                    return False
            return False
    
    async def send_priority(self, message: AgentMessage) -> bool:
        """Send a high-priority message (adds to front of queue)."""
        if message.is_expired():
            return False
        
        if message.receiver_id and message.receiver_id in self._queues:
            # For priority, we create a new queue with the message first
            # This is a simplification - a real implementation would use PriorityQueue
            queue = self._queues[message.receiver_id]
            try:
                # Put at front by creating new queue
                new_queue = asyncio.Queue(maxsize=self._max_queue_size)
                new_queue.put_nowait(message)
                while not queue.empty():
                    try:
                        new_queue.put_nowait(queue.get_nowait())
                    except asyncio.QueueFull:
                        break
                self._queues[message.receiver_id] = new_queue
                return True
            except Exception:
                return False
        return False
    
    async def receive(
        self,
        agent_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[AgentMessage]:
        """Receive a message for an agent."""
        if agent_id not in self._queues:
            return None
        
        queue = self._queues[agent_id]
        try:
            if timeout:
                message = await asyncio.wait_for(queue.get(), timeout=timeout)
            else:
                message = await queue.get()
            return message
        except asyncio.TimeoutError:
            return None
    
    async def publish(self, topic: str, message: AgentMessage) -> int:
        """
        Publish a message to a topic.
        
        Returns the number of agents that received the message.
        """
        count = 0
        subscribers = self._subscriptions.get(topic, [])
        
        for agent_id in subscribers:
            if agent_id in self._queues and agent_id != message.sender_id:
                try:
                    self._queues[agent_id].put_nowait(message)
                    count += 1
                except asyncio.QueueFull:
                    pass
        
        return count
    
    def get_queue_size(self, agent_id: str) -> int:
        """Get the number of pending messages for an agent."""
        if agent_id in self._queues:
            return self._queues[agent_id].qsize()
        return 0
    
    def get_history(
        self,
        agent_id: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        limit: int = 50,
    ) -> List[AgentMessage]:
        """Get message history, optionally filtered."""
        messages = self._history
        
        if agent_id:
            messages = [m for m in messages if m.sender_id == agent_id or m.receiver_id == agent_id]
        
        if message_type:
            messages = [m for m in messages if m.message_type == message_type]
        
        return messages[-limit:]
    
    def clear_history(self) -> None:
        """Clear message history."""
        self._history.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get communication bus statistics."""
        return {
            "registered_agents": len(self._queues),
            "total_subscriptions": sum(len(subs) for subs in self._subscriptions.values()),
            "history_size": len(self._history),
            "queue_sizes": {aid: q.qsize() for aid, q in self._queues.items()},
        }
