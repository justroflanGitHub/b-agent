#!/usr/bin/env python3
"""
Simple Browser API

REST API wrapper for the simple browser agent.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import asyncio
import logging

from simple_browser_agent import execute_browser_task, agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Simple Browser Agent API",
    description="Direct browser automation API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BrowserTaskRequest(BaseModel):
    """Request model for browser automation tasks."""
    goal: str
    url: str

# Removed BrowserTaskResponse model to avoid validation issues

@app.post("/execute-task")
async def execute_task(request: BrowserTaskRequest):
    """Execute a browser automation task."""
    try:
        logger.info(f"Executing task: {request.goal} on {request.url}")

        result = await execute_browser_task(request.goal, request.url)

        logger.info(f"Task result keys: {list(result.keys())}")
        logger.info(f"Task result: {result}")

        error_msg = result.get("error", "")
        if error_msg is None:
            error_msg = ""

        return {
            "task_id": result["task_id"],
            "status": result["status"],
            "goal": result["goal"],
            "results": result["results"],
            "success": result["success"],
            "execution_time": result["execution_time"],
            "error": error_msg
        }

    except Exception as e:
        logger.error(f"Task execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """Get system status."""
    browser_open = agent.browser is not None and agent.page is not None
    return {
        "status": "running",
        "message": "Simple Browser Agent API is active",
        "browser_mode": "visible",
        "browser_open": browser_open,
        "lm_studio_connected": True
    }

@app.post("/close-browser")
async def close_browser():
    """Close the browser window."""
    try:
        await agent.cleanup()
        return {
            "status": "success",
            "message": "Browser closed successfully"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to close browser: {str(e)}"
        }

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Simple Browser Agent API",
        "version": "1.0.0",
        "endpoints": [
            "POST /execute-task - Execute browser automation",
            "GET /status - Get system status",
            "POST /close-browser - Close browser window"
        ]
    }

if __name__ == "__main__":
    print("🚀 Starting Simple Browser Agent API...")
    print("📍 API available at: http://localhost:8080")
    print("🌐 Browser will be visible and on top of other applications")
    print("Press Ctrl+C to exit")
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
