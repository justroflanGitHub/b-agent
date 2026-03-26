"""
Browser Agent API Models

Pydantic models for request/response validation.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TaskStatusEnum(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SkillEnum(str, Enum):
    """Available skills enumeration."""
    FORM_FILLING = "form_filling"
    DATA_EXTRACTION = "data_extraction"
    WEB_SCRAPING = "web_scraping"
    WORKFLOW_AUTOMATION = "workflow_automation"


class TaskRequest(BaseModel):
    """Request model for creating a browser automation task."""
    goal: str = Field(..., description="Natural language goal for the task")
    start_url: Optional[str] = Field(None, description="Starting URL for the task")
    max_steps: int = Field(15, ge=1, le=100, description="Maximum number of steps")
    skill: Optional[SkillEnum] = Field(None, description="Optional skill to use")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Task configuration")
    priority: int = Field(5, ge=1, le=10, description="Task priority (1=lowest, 10=highest)")
    callback_url: Optional[str] = Field(None, description="Webhook URL for completion notification")

    class Config:
        json_schema_extra = {
            "example": {
                "goal": "Fill the contact form with name John Doe and email john@example.com",
                "start_url": "https://example.com/contact",
                "max_steps": 15,
                "skill": "form_filling",
                "config": {"timeout": 300},
                "priority": 5,
                "callback_url": None
            }
        }


class TaskStatus(BaseModel):
    """Response model for task status."""
    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatusEnum = Field(..., description="Current task status")
    goal: str = Field(..., description="Task goal")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Task progress (0-1)")
    current_step: int = Field(0, description="Current step number")
    total_steps: int = Field(0, description="Total estimated steps")
    created_at: datetime = Field(..., description="Task creation time")
    updated_at: datetime = Field(..., description="Last update time")
    started_at: Optional[datetime] = Field(None, description="Task start time")
    completed_at: Optional[datetime] = Field(None, description="Task completion time")
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_abc123",
                "status": "running",
                "goal": "Fill the contact form",
                "progress": 0.5,
                "current_step": 3,
                "total_steps": 6,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:32:00Z",
                "started_at": "2024-01-15T10:30:05Z",
                "completed_at": None,
                "error": None
            }
        }


class ActionResult(BaseModel):
    """Model for a single action result."""
    step: int = Field(..., description="Step number")
    action: str = Field(..., description="Action type")
    target: Optional[str] = Field(None, description="Target element description")
    success: bool = Field(..., description="Whether action succeeded")
    message: Optional[str] = Field(None, description="Action result message")
    timestamp: datetime = Field(..., description="Action timestamp")
    screenshot: Optional[str] = Field(None, description="Base64 screenshot (optional)")


class TaskResult(BaseModel):
    """Response model for completed task result."""
    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatusEnum = Field(..., description="Final task status")
    goal: str = Field(..., description="Task goal")
    success: bool = Field(..., description="Whether task succeeded")
    actions: List[ActionResult] = Field(default_factory=list, description="List of actions performed")
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Extracted data if any")
    final_url: Optional[str] = Field(None, description="Final URL after task")
    execution_time: float = Field(..., description="Total execution time in seconds")
    created_at: datetime = Field(..., description="Task creation time")
    completed_at: datetime = Field(..., description="Task completion time")
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_abc123",
                "status": "completed",
                "goal": "Fill the contact form",
                "success": True,
                "actions": [
                    {
                        "step": 1,
                        "action": "click",
                        "target": "Name input field",
                        "success": True,
                        "message": "Clicked on name field",
                        "timestamp": "2024-01-15T10:30:10Z",
                        "screenshot": None
                    }
                ],
                "extracted_data": None,
                "final_url": "https://example.com/contact",
                "execution_time": 45.2,
                "created_at": "2024-01-15T10:30:00Z",
                "completed_at": "2024-01-15T10:30:45Z",
                "error": None
            }
        }


class SessionInfo(BaseModel):
    """Model for browser session information."""
    session_id: str = Field(..., description="Session identifier")
    created_at: datetime = Field(..., description="Session creation time")
    last_activity: datetime = Field(..., description="Last activity time")
    status: str = Field(..., description="Session status")
    current_url: Optional[str] = Field(None, description="Current browser URL")
    task_count: int = Field(0, description="Number of tasks in session")
    active_tasks: int = Field(0, description="Number of active tasks")


class HealthStatus(BaseModel):
    """Model for health check response."""
    status: str = Field(..., description="Overall health status")
    version: str = Field(..., description="API version")
    uptime: float = Field(..., description="Uptime in seconds")
    browser_connected: bool = Field(..., description="Browser connection status")
    llm_connected: bool = Field(..., description="LLM connection status")
    active_tasks: int = Field(0, description="Number of active tasks")
    queued_tasks: int = Field(0, description="Number of queued tasks")
    memory_usage: Optional[float] = Field(None, description="Memory usage in MB")
    components: Dict[str, bool] = Field(default_factory=dict, description="Component health status")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "uptime": 3600.5,
                "browser_connected": True,
                "llm_connected": True,
                "active_tasks": 2,
                "queued_tasks": 5,
                "memory_usage": 256.5,
                "components": {
                    "browser": True,
                    "llm": True,
                    "vision": True,
                    "resilience": True
                }
            }
        }


class MetricPoint(BaseModel):
    """Model for a single metric data point."""
    timestamp: datetime = Field(..., description="Metric timestamp")
    value: float = Field(..., description="Metric value")


class MetricsResponse(BaseModel):
    """Response model for metrics."""
    task_duration: List[MetricPoint] = Field(default_factory=list, description="Task duration metrics")
    success_rate: List[MetricPoint] = Field(default_factory=list, description="Success rate metrics")
    error_types: Dict[str, int] = Field(default_factory=dict, description="Error type counts")
    action_latency: Dict[str, float] = Field(default_factory=dict, description="Average latency per action type")
    tasks_completed: int = Field(0, description="Total tasks completed")
    tasks_failed: int = Field(0, description="Total tasks failed")
    average_duration: float = Field(0.0, description="Average task duration")

    class Config:
        json_schema_extra = {
            "example": {
                "task_duration": [
                    {"timestamp": "2024-01-15T10:30:00Z", "value": 45.2}
                ],
                "success_rate": [
                    {"timestamp": "2024-01-15T10:30:00Z", "value": 0.95}
                ],
                "error_types": {
                    "timeout": 5,
                    "element_not_found": 3,
                    "navigation_error": 2
                },
                "action_latency": {
                    "click": 0.5,
                    "type": 0.3,
                    "scroll": 0.2
                },
                "tasks_completed": 100,
                "tasks_failed": 5,
                "average_duration": 42.5
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "TaskNotFoundError",
                "message": "Task with ID task_abc123 not found",
                "detail": {"task_id": "task_abc123"},
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


class SkillListResponse(BaseModel):
    """Response model for listing available skills."""
    skills: List[Dict[str, Any]] = Field(..., description="List of available skills")
    count: int = Field(..., description="Total number of skills")


class CancelResponse(BaseModel):
    """Response model for task cancellation."""
    task_id: str = Field(..., description="Cancelled task ID")
    status: TaskStatusEnum = Field(..., description="New task status")
    message: str = Field(..., description="Cancellation message")
