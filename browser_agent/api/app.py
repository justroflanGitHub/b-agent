"""
Browser Agent FastAPI Application

REST API for browser automation tasks.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import psutil

from .models import (
    TaskRequest,
    TaskStatus,
    TaskResult,
    TaskStatusEnum,
    SessionInfo,
    HealthStatus,
    MetricsResponse,
    MetricPoint,
    ErrorResponse,
    SkillListResponse,
    CancelResponse
)
from .task_manager import TaskManager


logger = logging.getLogger(__name__)

# Global state
task_manager: Optional[TaskManager] = None
app_start_time: float = 0
browser_connected: bool = False
llm_connected: bool = False


async def execute_browser_task(task_id: str, goal: str, start_url: Optional[str], max_steps: int):
    """
    Execute a browser automation task.
    
    This function integrates with the BrowserAgent.
    """
    global browser_connected, llm_connected
    
    try:
        # Import here to avoid circular imports
        from browser_agent import BrowserAgent
        from browser_agent.config import Config
        
        task = task_manager.tasks.get(task_id)
        if not task:
            return
        
        # Create agent
        config = Config.from_env()
        agent = BrowserAgent(config)
        
        # Initialize
        await agent.initialize()
        browser_connected = True
        llm_connected = True
        
        # Execute task
        result = await agent.execute_task(
            goal=goal,
            start_url=start_url,
            max_steps=max_steps
        )
        
        # Update task progress
        if result.get("success"):
            task_manager.complete_task(
                task_id,
                success=True,
                extracted_data=result.get("extracted_data"),
                final_url=result.get("final_url")
            )
        else:
            task_manager.set_task_error(
                task_id,
                result.get("error", "Unknown error"),
                "execution_error"
            )
        
        # Cleanup
        await agent.cleanup()
        
    except Exception as e:
        logger.error(f"Task execution error: {e}")
        task_manager.set_task_error(task_id, str(e), type(e).__name__)
        browser_connected = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global task_manager, app_start_time
    
    app_start_time = time.time()
    
    # Initialize task manager
    task_manager = TaskManager(
        max_concurrent_tasks=3,
        task_timeout=300.0,
        cleanup_interval=60.0
    )
    
    # Set task executor
    async def task_executor(task):
        await execute_browser_task(
            task.task_id,
            task.goal,
            task.start_url,
            task.max_steps
        )
    
    task_manager.on_task_start(task_executor)
    await task_manager.start()
    
    logger.info("Browser Agent API started")
    
    yield
    
    # Cleanup
    await task_manager.stop()
    logger.info("Browser Agent API stopped")


def create_app(
    title: str = "Browser Agent API",
    version: str = "1.0.0",
    cors_origins: list = None
) -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title=title,
        description="REST API for browser automation with visual intelligence",
        version=version,
        lifespan=lifespan
    )
    
    # CORS middleware
    if cors_origins is None:
        cors_origins = ["*"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=exc.__class__.__name__,
                message=str(exc.detail)
            ).model_dump(mode='json')
        )
    
    # Routes
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "Browser Agent API",
            "version": version,
            "status": "running",
            "endpoints": {
                "tasks": "/tasks",
                "health": "/health",
                "metrics": "/metrics",
                "skills": "/skills",
                "docs": "/docs"
            }
        }
    
    # Task endpoints
    @app.post(
        "/tasks",
        response_model=TaskStatus,
        status_code=201,
        tags=["Tasks"]
    )
    async def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
        """
        Submit a new browser automation task.
        
        The task will be queued and executed asynchronously.
        Use the returned task_id to check status and get results.
        """
        task_id = task_manager.submit_task(
            goal=request.goal,
            start_url=request.start_url,
            max_steps=request.max_steps,
            skill=request.skill.value if request.skill else None,
            config=request.config,
            priority=request.priority,
            callback_url=request.callback_url
        )
        
        # Start execution in background
        task = task_manager.tasks.get(task_id)
        background_tasks.add_task(
            execute_browser_task,
            task_id,
            request.goal,
            request.start_url,
            request.max_steps
        )
        
        return task_manager.get_task_status(task_id)
    
    @app.get("/tasks", response_model=list[TaskStatus], tags=["Tasks"])
    async def list_tasks(
        status: Optional[TaskStatusEnum] = Query(None, description="Filter by status"),
        limit: int = Query(50, ge=1, le=100, description="Max results"),
        offset: int = Query(0, ge=0, description="Offset for pagination")
    ):
        """
        List all tasks with optional filtering.
        
        Supports pagination and status filtering.
        """
        return task_manager.list_tasks(status=status, limit=limit, offset=offset)
    
    @app.get("/tasks/{task_id}", response_model=TaskStatus, tags=["Tasks"])
    async def get_task_status(task_id: str):
        """
        Get the current status of a task.
        
        Returns progress, current step, and timing information.
        """
        status = task_manager.get_task_status(task_id)
        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )
        return status
    
    @app.get("/tasks/{task_id}/result", response_model=TaskResult, tags=["Tasks"])
    async def get_task_result(task_id: str):
        """
        Get the result of a completed task.
        
        Only available for completed tasks.
        """
        status = task_manager.get_task_status(task_id)
        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )
        
        if status.status not in (TaskStatusEnum.COMPLETED, TaskStatusEnum.FAILED):
            raise HTTPException(
                status_code=400,
                detail=f"Task is not complete (status: {status.status})"
            )
        
        result = task_manager.get_task_result(task_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Result not found for task {task_id}"
            )
        return result
    
    @app.post("/tasks/{task_id}/cancel", response_model=CancelResponse, tags=["Tasks"])
    async def cancel_task(task_id: str):
        """
        Cancel a running or pending task.
        
        Cannot cancel completed or already cancelled tasks.
        """
        status = task_manager.get_task_status(task_id)
        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )
        
        if not task_manager.cancel_task(task_id):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel task with status {status.status}"
            )
        
        return CancelResponse(
            task_id=task_id,
            status=TaskStatusEnum.CANCELLED,
            message=f"Task {task_id} cancelled successfully"
        )
    
    @app.delete("/tasks/{task_id}", tags=["Tasks"])
    async def delete_task(task_id: str):
        """
        Delete a task from history.
        
        Only completed, failed, or cancelled tasks can be deleted.
        """
        status = task_manager.get_task_status(task_id)
        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )
        
        if status.status == TaskStatusEnum.RUNNING:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete running task. Cancel first."
            )
        
        if task_id in task_manager.tasks:
            del task_manager.tasks[task_id]
        
        return {"message": f"Task {task_id} deleted"}
    
    # Health endpoints
    @app.get("/health", response_model=HealthStatus, tags=["Health"])
    async def health_check():
        """
        Get system health status.
        
        Returns connection status, active tasks, and component health.
        """
        uptime = time.time() - app_start_time
        
        # Get memory usage
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        return HealthStatus(
            status="healthy" if browser_connected and llm_connected else "degraded",
            version=version,
            uptime=uptime,
            browser_connected=browser_connected,
            llm_connected=llm_connected,
            active_tasks=len(task_manager.active_tasks),
            queued_tasks=len(task_manager.priority_queue),
            memory_usage=memory_mb,
            components={
                "browser": browser_connected,
                "llm": llm_connected,
                "vision": llm_connected,  # Same as LLM for now
                "resilience": True
            }
        )
    
    @app.get("/health/ready", tags=["Health"])
    async def readiness_check():
        """Check if the service is ready to accept requests."""
        if not task_manager:
            raise HTTPException(status_code=503, detail="Task manager not initialized")
        
        return {"status": "ready"}
    
    @app.get("/health/live", tags=["Health"])
    async def liveness_check():
        """Check if the service is alive."""
        return {"status": "alive"}
    
    # Metrics endpoints
    @app.get("/metrics", response_model=MetricsResponse, tags=["Metrics"])
    async def get_metrics():
        """
        Get task execution metrics.
        
        Returns success rates, durations, and error statistics.
        """
        metrics = task_manager.get_metrics()
        
        # Convert to metric points (simplified - would normally have time series)
        now = datetime.utcnow()
        
        return MetricsResponse(
            task_duration=[
                MetricPoint(timestamp=now, value=d)
                for d in metrics.get("task_durations", [])[-10:]
            ],
            success_rate=[
                MetricPoint(
                    timestamp=now,
                    value=metrics["tasks_completed"] / 
                          (metrics["tasks_completed"] + metrics["tasks_failed"])
                    if (metrics["tasks_completed"] + metrics["tasks_failed"]) > 0
                    else 0
                )
            ],
            error_types=metrics.get("error_types", {}),
            action_latency=metrics.get("action_latency", {}),
            tasks_completed=metrics.get("tasks_completed", 0),
            tasks_failed=metrics.get("tasks_failed", 0),
            average_duration=metrics.get("average_duration", 0.0)
        )
    
    @app.get("/metrics/prometheus", tags=["Metrics"])
    async def get_prometheus_metrics():
        """
        Get metrics in Prometheus format.
        
        For integration with Prometheus monitoring.
        """
        metrics = task_manager.get_metrics()
        
        lines = [
            "# HELP browser_agent_tasks_completed Total completed tasks",
            "# TYPE browser_agent_tasks_completed counter",
            f"browser_agent_tasks_completed {metrics.get('tasks_completed', 0)}",
            "",
            "# HELP browser_agent_tasks_failed Total failed tasks",
            "# TYPE browser_agent_tasks_failed counter",
            f"browser_agent_tasks_failed {metrics.get('tasks_failed', 0)}",
            "",
            "# HELP browser_agent_tasks_cancelled Total cancelled tasks",
            "# TYPE browser_agent_tasks_cancelled counter",
            f"browser_agent_tasks_cancelled {metrics.get('tasks_cancelled', 0)}",
            "",
            "# HELP browser_agent_active_tasks Currently active tasks",
            "# TYPE browser_agent_active_tasks gauge",
            f"browser_agent_active_tasks {metrics.get('active_tasks', 0)}",
            "",
            "# HELP browser_agent_queued_tasks Tasks waiting in queue",
            "# TYPE browser_agent_queued_tasks gauge",
            f"browser_agent_queued_tasks {metrics.get('queued_tasks', 0)}",
            "",
            "# HELP browser_agent_average_duration Average task duration in seconds",
            "# TYPE browser_agent_average_duration gauge",
            f"browser_agent_average_duration {metrics.get('average_duration', 0):.2f}",
        ]
        
        return "\n".join(lines), {"Content-Type": "text/plain"}
    
    # Skills endpoints
    @app.get("/skills", response_model=SkillListResponse, tags=["Skills"])
    async def list_skills():
        """
        List available skills.
        
        Skills are specialized automation patterns for common tasks.
        """
        skills = [
            {
                "name": "form_filling",
                "description": "Multi-field form completion with validation",
                "version": "1.0.0",
                "actions": ["click", "type", "select", "check"]
            },
            {
                "name": "data_extraction",
                "description": "Structured extraction from dynamic pages",
                "version": "1.0.0",
                "actions": ["extract", "scroll", "paginate"]
            },
            {
                "name": "web_scraping",
                "description": "Multi-page navigation and data aggregation",
                "version": "1.0.0",
                "actions": ["navigate", "extract", "scroll", "click"]
            },
            {
                "name": "workflow_automation",
                "description": "Chained operations with conditional logic",
                "version": "1.0.0",
                "actions": ["navigate", "click", "type", "wait", "verify"]
            }
        ]
        
        return SkillListResponse(skills=skills, count=len(skills))
    
    @app.post("/skills/{skill_name}/execute", response_model=TaskStatus, tags=["Skills"])
    async def execute_skill(
        skill_name: str,
        request: TaskRequest,
        background_tasks: BackgroundTasks
    ):
        """
        Execute a specific skill.
        
        Skill execution is optimized for the skill's use case.
        """
        # Validate skill
        valid_skills = ["form_filling", "data_extraction", "web_scraping", "workflow_automation"]
        if skill_name not in valid_skills:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown skill: {skill_name}. Valid skills: {valid_skills}"
            )
        
        # Submit task with skill
        task_id = task_manager.submit_task(
            goal=request.goal,
            start_url=request.start_url,
            max_steps=request.max_steps,
            skill=skill_name,
            config=request.config,
            priority=request.priority,
            callback_url=request.callback_url
        )
        
        # Start execution
        background_tasks.add_task(
            execute_browser_task,
            task_id,
            request.goal,
            request.start_url,
            request.max_steps
        )
        
        return task_manager.get_task_status(task_id)
    
    # Session endpoints
    @app.get("/sessions", response_model=list[SessionInfo], tags=["Sessions"])
    async def list_sessions():
        """
        List browser sessions.
        
        Sessions represent browser instances with their state.
        """
        # Simplified - would normally track actual sessions
        return [
            SessionInfo(
                session_id="default",
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                status="active" if browser_connected else "inactive",
                current_url=None,
                task_count=len(task_manager.tasks),
                active_tasks=len(task_manager.active_tasks)
            )
        ]
    
    @app.post("/sessions/{session_id}/close", tags=["Sessions"])
    async def close_session(session_id: str):
        """
        Close a browser session.
        
        Cleans up browser resources.
        """
        global browser_connected
        
        if session_id != "default":
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        # Would normally close actual browser
        browser_connected = False
        
        return {"message": f"Session {session_id} closed"}
    
    # --- Credential Endpoints ---

    @app.post("/credentials", tags=["Credentials"])
    async def store_credential(request: dict):
        """
        Store a new credential in the vault.

        Body:
            alias: Credential alias (e.g., "salesforce_prod")
            tenant_id: Tenant ID (default: "default")
            credential_type: "password" | "api_key" | "oauth_token" | "cookie" | "certificate" | "ssh_key" | "custom"
            secret: The secret value
            username: Optional username
            metadata: Optional metadata dict
            expires_at: Optional ISO datetime
            rotation_policy: "none" | "on_use" | "time_based" | "on_failure"
            rotation_interval_days: Days between rotations (default: 90)
        """
        try:
            from browser_agent.security import CredentialVault, CredentialType, RotationPolicy
            vault = _get_credential_vault()
            if vault is None:
                raise HTTPException(status_code=503, detail="Credential vault not configured")

            cred_type = CredentialType(request.get("credential_type", "password"))
            rot_policy = RotationPolicy(request.get("rotation_policy", "none"))
            expires = request.get("expires_at")
            expires_dt = datetime.fromisoformat(expires) if expires else None

            entry = await vault.store_credential(
                alias=request["alias"],
                tenant_id=request.get("tenant_id", "default"),
                credential_type=cred_type,
                secret=request["secret"],
                username=request.get("username"),
                metadata=request.get("metadata", {}),
                expires_at=expires_dt,
                rotation_policy=rot_policy,
                rotation_interval_days=request.get("rotation_interval_days", 90),
                created_by=request.get("created_by", "api"),
            )
            return {
                "credential_id": entry.credential_id,
                "alias": entry.alias,
                "credential_type": entry.credential_type.value,
                "created_at": entry.created_at.isoformat(),
            }
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Missing required field: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/credentials", tags=["Credentials"])
    async def list_credentials(tenant_id: str = Query("default")):
        """List credential summaries (never returns secrets)."""
        try:
            vault = _get_credential_vault()
            if vault is None:
                raise HTTPException(status_code=503, detail="Credential vault not configured")
            summaries = await vault.list_credentials(tenant_id)
            return [
                {
                    "credential_id": s.credential_id,
                    "alias": s.alias,
                    "tenant_id": s.tenant_id,
                    "credential_type": s.credential_type.value,
                    "username": s.username,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                    "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                    "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None,
                    "access_count": s.access_count,
                    "rotation_policy": s.rotation_policy.value,
                    "is_expired": s.is_expired,
                }
                for s in summaries
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/credentials/{alias}", tags=["Credentials"])
    async def get_credential_metadata(alias: str, tenant_id: str = Query("default")):
        """Get credential metadata (never returns the secret)."""
        try:
            vault = _get_credential_vault()
            if vault is None:
                raise HTTPException(status_code=503, detail="Credential vault not configured")
            summary = await vault.get_credential_summary(alias, tenant_id)
            if summary is None:
                raise HTTPException(status_code=404, detail=f"Credential '{alias}' not found")
            return {
                "credential_id": summary.credential_id,
                "alias": summary.alias,
                "tenant_id": summary.tenant_id,
                "credential_type": summary.credential_type.value,
                "username": summary.username,
                "metadata": summary.metadata,
                "created_at": summary.created_at.isoformat(),
                "updated_at": summary.updated_at.isoformat(),
                "expires_at": summary.expires_at.isoformat() if summary.expires_at else None,
                "last_used_at": summary.last_used_at.isoformat() if summary.last_used_at else None,
                "access_count": summary.access_count,
                "rotation_policy": summary.rotation_policy.value,
                "is_expired": summary.is_expired,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.put("/credentials/{alias}", tags=["Credentials"])
    async def update_credential(alias: str, request: dict):
        """Update credential metadata or rotate secret."""
        try:
            vault = _get_credential_vault()
            if vault is None:
                raise HTTPException(status_code=503, detail="Credential vault not configured")
            tenant_id = request.get("tenant_id", "default")

            if "new_secret" in request:
                entry = await vault.rotate_credential(
                    alias=alias,
                    tenant_id=tenant_id,
                    new_secret=request["new_secret"],
                    rotated_by=request.get("rotated_by", "api"),
                )
            else:
                entry = await vault.update_metadata(
                    alias=alias,
                    tenant_id=tenant_id,
                    metadata=request.get("metadata"),
                    username=request.get("username"),
                    expires_at=request.get("expires_at"),
                )

            if entry is None:
                raise HTTPException(status_code=404, detail=f"Credential '{alias}' not found")

            return {"alias": alias, "updated_at": entry.updated_at.isoformat()}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/credentials/{alias}", tags=["Credentials"])
    async def delete_credential(alias: str, tenant_id: str = Query("default")):
        """Delete a credential from the vault."""
        try:
            vault = _get_credential_vault()
            if vault is None:
                raise HTTPException(status_code=503, detail="Credential vault not configured")
            deleted = await vault.delete_credential(alias, tenant_id)
            if not deleted:
                raise HTTPException(status_code=404, detail=f"Credential '{alias}' not found")
            return {"alias": alias, "deleted": True}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/credentials/{alias}/rotate", tags=["Credentials"])
    async def rotate_credential(alias: str, request: dict):
        """Rotate a credential's secret."""
        try:
            vault = _get_credential_vault()
            if vault is None:
                raise HTTPException(status_code=503, detail="Credential vault not configured")
            entry = await vault.rotate_credential(
                alias=alias,
                tenant_id=request.get("tenant_id", "default"),
                new_secret=request["new_secret"],
                rotated_by=request.get("rotated_by", "api"),
            )
            return {"alias": alias, "rotated_at": entry.updated_at.isoformat()}
        except KeyError as e:
            raise HTTPException(status_code=400, detail=f"Missing required field: {e}")
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Credential '{alias}' not found")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # --- Audit Endpoints ---

    @app.get("/audit/events", tags=["Audit"])
    async def query_audit_events(
        tenant_id: str = Query("default"),
        task_id: Optional[str] = Query(None),
        event_type: Optional[str] = Query(None),
        start_time: Optional[str] = Query(None),
        end_time: Optional[str] = Query(None),
        limit: int = Query(100, le=1000),
        offset: int = Query(0, ge=0),
    ):
        """Query audit events with filters."""
        try:
            audit = _get_audit_log()
            if audit is None:
                raise HTTPException(status_code=503, detail="Audit log not configured")

            from browser_agent.compliance import AuditEventType
            from browser_agent.compliance.audit_log import AuditFilter, SensitivityLevel
            from datetime import datetime as dt

            event_types = None
            if event_type:
                event_types = [AuditEventType(event_type)]

            filters = AuditFilter(
                tenant_id=tenant_id,
                task_id=task_id,
                event_types=event_types,
                start_time=dt.fromisoformat(start_time) if start_time else None,
                end_time=dt.fromisoformat(end_time) if end_time else None,
                limit=limit,
                offset=offset,
            )

            events = await audit.query(filters)
            return [e.to_dict() for e in events]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/audit/tasks/{task_id}/timeline", tags=["Audit"])
    async def get_task_timeline(task_id: str, tenant_id: str = Query("default")):
        """Get full timeline of events for a task."""
        try:
            audit = _get_audit_log()
            if audit is None:
                raise HTTPException(status_code=503, detail="Audit log not configured")
            timeline = await audit.get_task_timeline(task_id, tenant_id)
            return {
                "task_id": timeline.task_id,
                "total_duration": timeline.total_duration,
                "action_count": timeline.action_count,
                "success_count": timeline.success_count,
                "failure_count": timeline.failure_count,
                "events": [e.to_dict() for e in timeline.events],
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/audit/verify-chain", tags=["Audit"])
    async def verify_chain(tenant_id: str = Query("default")):
        """Verify integrity of the audit chain."""
        try:
            audit = _get_audit_log()
            if audit is None:
                raise HTTPException(status_code=503, detail="Audit log not configured")
            result = await audit.verify_chain(tenant_id)
            return {
                "total_events": result.total_events,
                "verified_events": result.verified_events,
                "is_valid": result.is_valid,
                "tampered_events": len(result.tampered_events),
                "missing_events": len(result.missing_events),
                "verification_time": result.verification_time,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/audit/export", tags=["Audit"])
    async def export_audit(
        format: str = Query("json"),
        tenant_id: str = Query("default"),
        start_time: Optional[str] = Query(None),
        end_time: Optional[str] = Query(None),
    ):
        """Export audit events in various formats."""
        try:
            audit = _get_audit_log()
            if audit is None:
                raise HTTPException(status_code=503, detail="Audit log not configured")

            from browser_agent.compliance.audit_log import AuditFilter
            from browser_agent.compliance.export import AuditExporter
            from datetime import datetime as dt

            filters = AuditFilter(
                tenant_id=tenant_id,
                start_time=dt.fromisoformat(start_time) if start_time else None,
                end_time=dt.fromisoformat(end_time) if end_time else None,
                limit=100000,
            )
            events = await audit.query(filters)

            if format == "csv":
                return JSONResponse(content={"data": AuditExporter.to_csv(events)})
            elif format == "cef":
                return JSONResponse(content={"data": AuditExporter.to_cef(events)})
            elif format == "syslog":
                return JSONResponse(content={"data": AuditExporter.to_syslog(events)})
            else:
                return JSONResponse(content={"data": AuditExporter.to_json(events)})
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/audit/compliance-report", tags=["Audit"])
    async def compliance_report(
        framework: str = Query("soc2"),
        tenant_id: str = Query("default"),
        start_date: str = Query(...),
        end_date: str = Query(...),
    ):
        """Generate a compliance report."""
        try:
            audit = _get_audit_log()
            if audit is None:
                raise HTTPException(status_code=503, detail="Audit log not configured")
            from datetime import datetime as dt

            report = await audit.generate_compliance_report(
                framework=framework,
                start_date=dt.fromisoformat(start_date),
                end_date=dt.fromisoformat(end_date),
                tenant_id=tenant_id,
            )
            return report.to_dict()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/audit/statistics", tags=["Audit"])
    async def audit_statistics(tenant_id: str = Query("default")):
        """Get audit statistics."""
        try:
            audit = _get_audit_log()
            if audit is None:
                raise HTTPException(status_code=503, detail="Audit log not configured")
            from browser_agent.compliance.audit_log import AuditFilter

            total = await audit._store.count(AuditFilter(tenant_id=tenant_id, limit=1))
            return {"tenant_id": tenant_id, "total_events": total}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


# Vault singleton (initialized on first use)
_credential_vault = None


def _get_credential_vault():
    """Get or create the credential vault singleton."""
    global _credential_vault
    if _credential_vault is not None:
        return _credential_vault

    try:
        from browser_agent.security import CredentialVault
        import base64
        import os

        master_key_b64 = os.environ.get("CREDS_MASTER_KEY")
        if not master_key_b64:
            return None

        master_key = base64.b64decode(master_key_b64)
        store_type = os.environ.get("CREDS_STORE_TYPE", "file")
        store_path = os.environ.get("CREDS_STORE_PATH", ".credentials")

        _credential_vault = CredentialVault.from_config({
            "master_key": master_key,
            "store_type": store_type,
            "store_path": store_path,
        })
        return _credential_vault
    except Exception as e:
        logger.warning("Failed to initialize credential vault: %s", e)
        return None


# Audit log singleton
_audit_log = None


def _get_audit_log():
    """Get or create the audit log singleton."""
    global _audit_log
    if _audit_log is not None:
        return _audit_log

    try:
        from browser_agent.compliance import AuditLog
        import os

        enabled = os.environ.get("AUDIT_ENABLED", "false").lower()
        if enabled != "true":
            return None

        store_path = os.environ.get("AUDIT_STORE_PATH", ".audit")
        _audit_log = AuditLog.from_config({
            "store_type": os.environ.get("AUDIT_STORE_TYPE", "sqlite"),
            "store_path": store_path,
            "chain_key_env": "AUDIT_CHAIN_KEY",
        })
        return _audit_log
    except Exception as e:
        logger.warning("Failed to initialize audit log: %s", e)
        return None


# Default app instance
app = create_app()
