"""
Tests for Browser Agent API

Tests for FastAPI endpoints, task manager, and models.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import json

from fastapi.testclient import TestClient
from httpx import AsyncClient

from browser_agent.api.models import (
    TaskRequest,
    TaskStatus,
    TaskResult,
    TaskStatusEnum,
    SkillEnum,
    ActionResult,
    HealthStatus,
    MetricsResponse,
    ErrorResponse
)
from browser_agent.api.task_manager import TaskManager, Task, TaskPriority


# ============= Model Tests =============

class TestTaskRequest:
    """Tests for TaskRequest model."""
    
    def test_task_request_minimal(self):
        """Test minimal task request."""
        request = TaskRequest(goal="Test goal")
        assert request.goal == "Test goal"
        assert request.start_url is None
        assert request.max_steps == 15
        assert request.skill is None
        assert request.config == {}
        assert request.priority == 5
        assert request.callback_url is None
    
    def test_task_request_full(self):
        """Test full task request."""
        request = TaskRequest(
            goal="Fill form",
            start_url="https://example.com",
            max_steps=20,
            skill=SkillEnum.FORM_FILLING,
            config={"timeout": 60},
            priority=8,
            callback_url="https://callback.example.com"
        )
        assert request.goal == "Fill form"
        assert request.start_url == "https://example.com"
        assert request.max_steps == 20
        assert request.skill == SkillEnum.FORM_FILLING
        assert request.config == {"timeout": 60}
        assert request.priority == 8
        assert request.callback_url == "https://callback.example.com"
    
    def test_task_request_validation_max_steps(self):
        """Test max_steps validation."""
        # Valid range
        request = TaskRequest(goal="Test", max_steps=50)
        assert request.max_steps == 50
        
        # Invalid - too low
        with pytest.raises(ValueError):
            TaskRequest(goal="Test", max_steps=0)
        
        # Invalid - too high
        with pytest.raises(ValueError):
            TaskRequest(goal="Test", max_steps=150)
    
    def test_task_request_validation_priority(self):
        """Test priority validation."""
        # Valid range
        request = TaskRequest(goal="Test", priority=1)
        assert request.priority == 1
        
        request = TaskRequest(goal="Test", priority=10)
        assert request.priority == 10
        
        # Invalid - too low
        with pytest.raises(ValueError):
            TaskRequest(goal="Test", priority=0)
        
        # Invalid - too high
        with pytest.raises(ValueError):
            TaskRequest(goal="Test", priority=11)


class TestTaskStatus:
    """Tests for TaskStatus model."""
    
    def test_task_status_creation(self):
        """Test task status creation."""
        now = datetime.utcnow()
        status = TaskStatus(
            task_id="task_123",
            status=TaskStatusEnum.RUNNING,
            goal="Test goal",
            progress=0.5,
            current_step=3,
            total_steps=6,
            created_at=now,
            updated_at=now,
            started_at=now
        )
        assert status.task_id == "task_123"
        assert status.status == TaskStatusEnum.RUNNING
        assert status.progress == 0.5
        assert status.current_step == 3
        assert status.total_steps == 6
    
    def test_task_status_progress_validation(self):
        """Test progress validation (0-1)."""
        now = datetime.utcnow()
        
        # Valid
        status = TaskStatus(
            task_id="task_123",
            status=TaskStatusEnum.PENDING,
            goal="Test",
            progress=0.0,
            current_step=0,
            total_steps=0,
            created_at=now,
            updated_at=now
        )
        assert status.progress == 0.0
        
        # Valid
        status = TaskStatus(
            task_id="task_123",
            status=TaskStatusEnum.COMPLETED,
            goal="Test",
            progress=1.0,
            current_step=5,
            total_steps=5,
            created_at=now,
            updated_at=now
        )
        assert status.progress == 1.0
        
        # Invalid - negative
        with pytest.raises(ValueError):
            TaskStatus(
                task_id="task_123",
                status=TaskStatusEnum.PENDING,
                goal="Test",
                progress=-0.1,
                current_step=0,
                total_steps=0,
                created_at=now,
                updated_at=now
            )


class TestActionResult:
    """Tests for ActionResult model."""
    
    def test_action_result_creation(self):
        """Test action result creation."""
        now = datetime.utcnow()
        result = ActionResult(
            step=1,
            action="click",
            target="Submit button",
            success=True,
            message="Clicked successfully",
            timestamp=now
        )
        assert result.step == 1
        assert result.action == "click"
        assert result.target == "Submit button"
        assert result.success is True
        assert result.screenshot is None


class TestTaskResult:
    """Tests for TaskResult model."""
    
    def test_task_result_creation(self):
        """Test task result creation."""
        now = datetime.utcnow()
        action = ActionResult(
            step=1,
            action="click",
            target="Button",
            success=True,
            timestamp=now
        )
        result = TaskResult(
            task_id="task_123",
            status=TaskStatusEnum.COMPLETED,
            goal="Test goal",
            success=True,
            actions=[action],
            execution_time=10.5,
            created_at=now,
            completed_at=now
        )
        assert result.task_id == "task_123"
        assert result.success is True
        assert len(result.actions) == 1
        assert result.execution_time == 10.5


class TestHealthStatus:
    """Tests for HealthStatus model."""
    
    def test_health_status_healthy(self):
        """Test healthy status."""
        status = HealthStatus(
            status="healthy",
            version="1.0.0",
            uptime=3600.0,
            browser_connected=True,
            llm_connected=True,
            active_tasks=2,
            queued_tasks=5,
            memory_usage=256.5,
            components={"browser": True, "llm": True}
        )
        assert status.status == "healthy"
        assert status.browser_connected is True
        assert status.llm_connected is True


class TestMetricsResponse:
    """Tests for MetricsResponse model."""
    
    def test_metrics_response_creation(self):
        """Test metrics response creation."""
        now = datetime.utcnow()
        metrics = MetricsResponse(
            task_duration=[{"timestamp": now, "value": 45.2}],
            success_rate=[{"timestamp": now, "value": 0.95}],
            error_types={"timeout": 5},
            action_latency={"click": 0.5},
            tasks_completed=100,
            tasks_failed=5,
            average_duration=42.5
        )
        assert metrics.tasks_completed == 100
        assert metrics.tasks_failed == 5
        assert metrics.average_duration == 42.5


# ============= Task Manager Tests =============

class TestTaskPriority:
    """Tests for TaskPriority."""
    
    def test_priority_ordering(self):
        """Test priority queue ordering."""
        # Higher priority should come first
        p1 = TaskPriority(priority=5, task_id="task1", created_at=1.0)
        p2 = TaskPriority(priority=10, task_id="task2", created_at=2.0)
        p3 = TaskPriority(priority=5, task_id="task3", created_at=0.5)
        
        # p2 has highest priority
        assert p2 < p1
        # Same priority, earlier created_at wins
        assert p3 < p1


class TestTaskManager:
    """Tests for TaskManager."""
    
    @pytest.fixture
    def task_manager(self):
        """Create task manager for testing."""
        return TaskManager(
            max_concurrent_tasks=2,
            task_timeout=60.0,
            cleanup_interval=10.0
        )
    
    def test_submit_task(self, task_manager):
        """Test task submission."""
        task_id = task_manager.submit_task(
            goal="Test goal",
            start_url="https://example.com",
            max_steps=10
        )
        
        assert task_id.startswith("task_")
        assert task_id in task_manager.tasks
        
        task = task_manager.tasks[task_id]
        assert task.goal == "Test goal"
        assert task.start_url == "https://example.com"
        assert task.status == TaskStatusEnum.PENDING
    
    def test_submit_task_with_priority(self, task_manager):
        """Test task submission with priority."""
        task_id_low = task_manager.submit_task(goal="Low priority", priority=1)
        task_id_high = task_manager.submit_task(goal="High priority", priority=10)
        
        # High priority should be first in queue
        assert task_manager.priority_queue[0].task_id == task_id_high
    
    def test_get_task_status(self, task_manager):
        """Test getting task status."""
        task_id = task_manager.submit_task(goal="Test")
        
        status = task_manager.get_task_status(task_id)
        assert status is not None
        assert status.task_id == task_id
        assert status.status == TaskStatusEnum.PENDING
    
    def test_get_task_status_not_found(self, task_manager):
        """Test getting status for non-existent task."""
        status = task_manager.get_task_status("nonexistent")
        assert status is None
    
    def test_cancel_task(self, task_manager):
        """Test task cancellation."""
        task_id = task_manager.submit_task(goal="Test")
        
        result = task_manager.cancel_task(task_id)
        assert result is True
        
        task = task_manager.tasks[task_id]
        assert task.status == TaskStatusEnum.CANCELLED
    
    def test_cancel_completed_task(self, task_manager):
        """Test cancelling already completed task."""
        task_id = task_manager.submit_task(goal="Test")
        task = task_manager.tasks[task_id]
        task.status = TaskStatusEnum.COMPLETED
        
        result = task_manager.cancel_task(task_id)
        assert result is False
    
    def test_list_tasks(self, task_manager):
        """Test listing tasks."""
        task_id1 = task_manager.submit_task(goal="Task 1")
        task_id2 = task_manager.submit_task(goal="Task 2")
        
        tasks = task_manager.list_tasks()
        assert len(tasks) == 2
    
    def test_list_tasks_with_status_filter(self, task_manager):
        """Test listing tasks with status filter."""
        task_id1 = task_manager.submit_task(goal="Task 1")
        task_id2 = task_manager.submit_task(goal="Task 2")
        
        # Cancel one task
        task_manager.cancel_task(task_id2)
        
        pending_tasks = task_manager.list_tasks(status=TaskStatusEnum.PENDING)
        assert len(pending_tasks) == 1
        assert pending_tasks[0].task_id == task_id1
        
        cancelled_tasks = task_manager.list_tasks(status=TaskStatusEnum.CANCELLED)
        assert len(cancelled_tasks) == 1
        assert cancelled_tasks[0].task_id == task_id2
    
    def test_list_tasks_pagination(self, task_manager):
        """Test task list pagination."""
        for i in range(10):
            task_manager.submit_task(goal=f"Task {i}")
        
        # Get first 5
        page1 = task_manager.list_tasks(limit=5, offset=0)
        assert len(page1) == 5
        
        # Get next 5
        page2 = task_manager.list_tasks(limit=5, offset=5)
        assert len(page2) == 5
    
    def test_update_task_progress(self, task_manager):
        """Test updating task progress."""
        task_id = task_manager.submit_task(goal="Test")
        
        task_manager.update_task_progress(
            task_id,
            current_step=3,
            total_steps=10
        )
        
        task = task_manager.tasks[task_id]
        assert task.current_step == 3
        assert task.total_steps == 10
        assert task.progress == 0.3
    
    def test_set_task_error(self, task_manager):
        """Test setting task error."""
        task_id = task_manager.submit_task(goal="Test")
        
        task_manager.set_task_error(
            task_id,
            error="Something went wrong",
            error_type="timeout"
        )
        
        task = task_manager.tasks[task_id]
        assert task.status == TaskStatusEnum.FAILED
        assert task.error == "Something went wrong"
        assert task_manager.metrics["error_types"]["timeout"] == 1
    
    def test_complete_task(self, task_manager):
        """Test completing task."""
        task_id = task_manager.submit_task(goal="Test")
        task = task_manager.tasks[task_id]
        task.started_at = datetime.utcnow()
        
        task_manager.complete_task(
            task_id,
            success=True,
            extracted_data={"key": "value"},
            final_url="https://example.com/result"
        )
        
        task = task_manager.tasks[task_id]
        assert task.status == TaskStatusEnum.COMPLETED
        assert task.extracted_data == {"key": "value"}
        assert task.final_url == "https://example.com/result"
        assert task.result is not None
        assert task.result.success is True
    
    def test_get_metrics(self, task_manager):
        """Test getting metrics."""
        # Submit and complete some tasks
        task_id = task_manager.submit_task(goal="Test")
        task = task_manager.tasks[task_id]
        task.started_at = datetime.utcnow()
        task_manager.complete_task(task_id, success=True)
        
        task_id2 = task_manager.submit_task(goal="Test 2")
        task_manager.set_task_error(task_id2, "Error", "test_error")
        
        metrics = task_manager.get_metrics()
        
        assert metrics["tasks_completed"] == 1
        assert metrics["tasks_failed"] == 1
        assert "test_error" in metrics["error_types"]
    
    @pytest.mark.asyncio
    async def test_task_manager_start_stop(self, task_manager):
        """Test starting and stopping task manager."""
        await task_manager.start()
        assert task_manager._running is True
        
        await task_manager.stop()
        assert task_manager._running is False


# ============= API Endpoint Tests =============

class TestAPIEndpoints:
    """Tests for FastAPI endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client with initialized task manager."""
        from browser_agent.api.app import create_app, task_manager as tm
        import browser_agent.api.app as api_module
        
        app = create_app()
        
        # Initialize task manager for testing
        from browser_agent.api.task_manager import TaskManager
        api_module.task_manager = TaskManager(
            max_concurrent_tasks=2,
            task_timeout=60.0
        )
        
        with TestClient(app) as client:
            yield client
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "endpoints" in data
    
    def test_health_endpoint(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "uptime" in data
        assert "browser_connected" in data
        assert "llm_connected" in data
    
    def test_health_ready_endpoint(self, client):
        """Test readiness endpoint."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
    
    def test_health_live_endpoint(self, client):
        """Test liveness endpoint."""
        response = client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
    
    def test_list_skills(self, client):
        """Test listing skills."""
        response = client.get("/skills")
        assert response.status_code == 200
        data = response.json()
        assert "skills" in data
        assert "count" in data
        assert data["count"] >= 1
    
    def test_create_task(self, client):
        """Test creating a task."""
        response = client.post(
            "/tasks",
            json={
                "goal": "Test task",
                "start_url": "https://example.com",
                "max_steps": 10
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert "task_id" in data
        assert data["goal"] == "Test task"
        assert data["status"] in ["pending", "running"]
    
    def test_create_task_validation_error(self, client):
        """Test task creation with validation error."""
        response = client.post(
            "/tasks",
            json={
                "goal": "Test task",
                "max_steps": 200  # Invalid - too high
            }
        )
        assert response.status_code == 422
    
    def test_list_tasks(self, client):
        """Test listing tasks."""
        # Create a task first
        client.post("/tasks", json={"goal": "Test task"})
        
        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_list_tasks_with_filter(self, client):
        """Test listing tasks with status filter."""
        response = client.get("/tasks?status=pending")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_task_status(self, client):
        """Test getting task status."""
        # Create a task
        create_response = client.post(
            "/tasks",
            json={"goal": "Test task"}
        )
        task_id = create_response.json()["task_id"]
        
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
    
    def test_get_task_status_not_found(self, client):
        """Test getting status for non-existent task."""
        response = client.get("/tasks/nonexistent_task")
        assert response.status_code == 404
    
    def test_cancel_task(self, client):
        """Test cancelling a task."""
        # Create a task
        create_response = client.post(
            "/tasks",
            json={"goal": "Test task"}
        )
        task_id = create_response.json()["task_id"]
        
        # Task might already be running/completed due to background execution
        # Just verify the cancel endpoint works
        response = client.post(f"/tasks/{task_id}/cancel")
        # Accept 200 (cancelled) or 400 (already complete)
        assert response.status_code in [200, 400]
    
    def test_cancel_completed_task(self, client):
        """Test cancelling a completed task."""
        # Create a task
        create_response = client.post(
            "/tasks",
            json={"goal": "Test task"}
        )
        task_id = create_response.json()["task_id"]
        
        # Manually mark as completed using the module's task_manager
        import browser_agent.api.app as api_module
        if api_module.task_manager:
            task = api_module.task_manager.tasks.get(task_id)
            if task:
                task.status = TaskStatusEnum.COMPLETED
        
        response = client.post(f"/tasks/{task_id}/cancel")
        assert response.status_code == 400
    
    def test_get_metrics(self, client):
        """Test getting metrics."""
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "tasks_completed" in data
        assert "tasks_failed" in data
    
    def test_get_prometheus_metrics(self, client):
        """Test getting Prometheus metrics."""
        response = client.get("/metrics/prometheus")
        assert response.status_code == 200
        # Check it's plain text
        assert "browser_agent_tasks_completed" in response.text
    
    def test_list_sessions(self, client):
        """Test listing sessions."""
        response = client.get("/sessions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_close_session(self, client):
        """Test closing a session."""
        response = client.post("/sessions/default/close")
        assert response.status_code == 200
    
    def test_close_nonexistent_session(self, client):
        """Test closing non-existent session."""
        response = client.post("/sessions/nonexistent/close")
        assert response.status_code == 404
    
    def test_execute_skill(self, client):
        """Test executing a skill."""
        response = client.post(
            "/skills/form_filling/execute",
            json={
                "goal": "Fill the form",
                "start_url": "https://example.com/form"
            }
        )
        # Accept 201 (created) or 200 (if already processing)
        assert response.status_code in [200, 201]
        data = response.json()
        assert "task_id" in data
    
    def test_execute_invalid_skill(self, client):
        """Test executing invalid skill."""
        response = client.post(
            "/skills/invalid_skill/execute",
            json={"goal": "Test"}
        )
        assert response.status_code == 400


# ============= Integration Tests =============

class TestAPIIntegration:
    """Integration tests for API."""
    
    @pytest.fixture
    def client(self):
        """Create test client with initialized task manager."""
        from browser_agent.api.app import create_app
        import browser_agent.api.app as api_module
        
        app = create_app()
        
        # Initialize task manager for testing
        from browser_agent.api.task_manager import TaskManager
        api_module.task_manager = TaskManager(
            max_concurrent_tasks=2,
            task_timeout=60.0
        )
        
        with TestClient(app) as client:
            yield client
    
    def test_task_lifecycle(self, client):
        """Test complete task lifecycle."""
        # Create task
        create_response = client.post(
            "/tasks",
            json={
                "goal": "Test lifecycle",
                "max_steps": 5
            }
        )
        assert create_response.status_code == 201
        task_id = create_response.json()["task_id"]
        
        # Get status
        status_response = client.get(f"/tasks/{task_id}")
        assert status_response.status_code == 200
        assert status_response.json()["task_id"] == task_id
        
        # List tasks
        list_response = client.get("/tasks")
        assert list_response.status_code == 200
        task_ids = [t["task_id"] for t in list_response.json()]
        assert task_id in task_ids
        
        # Cancel task (may already be complete due to background execution)
        cancel_response = client.post(f"/tasks/{task_id}/cancel")
        # Accept 200 (cancelled) or 400 (already complete)
        assert cancel_response.status_code in [200, 400]
        
        # Verify final status is either cancelled or completed/failed
        final_status = client.get(f"/tasks/{task_id}")
        assert final_status.json()["status"] in ["cancelled", "completed", "failed", "running"]
    
    def test_multiple_tasks_priority(self, client):
        """Test multiple tasks with different priorities."""
        # Submit tasks with different priorities
        low_task = client.post(
            "/tasks",
            json={"goal": "Low priority", "priority": 1}
        )
        high_task = client.post(
            "/tasks",
            json={"goal": "High priority", "priority": 10}
        )
        medium_task = client.post(
            "/tasks",
            json={"goal": "Medium priority", "priority": 5}
        )
        
        assert low_task.status_code == 201
        assert high_task.status_code == 201
        assert medium_task.status_code == 201
        
        # All tasks should be listed
        list_response = client.get("/tasks")
        task_ids = [t["task_id"] for t in list_response.json()]
        
        assert low_task.json()["task_id"] in task_ids
        assert high_task.json()["task_id"] in task_ids
        assert medium_task.json()["task_id"] in task_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
