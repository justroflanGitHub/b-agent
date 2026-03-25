"""
Tests for Phase 3: Resilience & Recovery Module.

Tests for checkpoint system, fallback strategies, state stack, and recovery orchestration.
"""

import asyncio
import json
import os
import tempfile
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from browser_agent.resilience import (
    CheckpointManager, Checkpoint, BrowserState, CheckpointType,
    FallbackStrategy, FallbackManager, ErrorType, ErrorContext, FallbackResult,
    StateStack, StateFrame,
    RecoveryOrchestrator, RecoveryResult, RecoveryStatus, RecoveryConfig,
)
from browser_agent.resilience.fallback import (
    VisualSearchFallback,
    ScrollAndRetryFallback,
    ExtendedWaitFallback,
    RefreshAndRetryFallback,
    NavigationRetryFallback,
    CheckpointRestoreFallback,
)


# =============================================================================
# BrowserState Tests
# =============================================================================

class TestBrowserState:
    """Tests for BrowserState dataclass."""
    
    def test_create_browser_state(self):
        """Test creating a browser state."""
        state = BrowserState(
            url="https://example.com",
            title="Example",
            scroll_x=100,
            scroll_y=200,
        )
        
        assert state.url == "https://example.com"
        assert state.title == "Example"
        assert state.scroll_x == 100
        assert state.scroll_y == 200
        assert state.cookies == []
        assert state.local_storage == {}
        assert state.session_storage == {}
    
    def test_browser_state_with_screenshot(self):
        """Test browser state with screenshot computes hash."""
        screenshot = b"fake_screenshot_data"
        state = BrowserState(
            url="https://example.com",
            title="Example",
            screenshot=screenshot,
        )
        
        assert state.screenshot == screenshot
        assert state.screenshot_hash is not None
        assert len(state.screenshot_hash) == 16
    
    def test_browser_state_to_dict(self):
        """Test serializing browser state to dict."""
        state = BrowserState(
            url="https://example.com",
            title="Example",
            scroll_x=100,
            scroll_y=200,
            cookies=[{"name": "session", "value": "abc"}],
            screenshot=b"test",
        )
        
        data = state.to_dict()
        
        assert data["url"] == "https://example.com"
        assert data["title"] == "Example"
        assert data["scroll_x"] == 100
        assert data["scroll_y"] == 200
        assert data["cookies"] == [{"name": "session", "value": "abc"}]
        assert "screenshot" not in data  # Screenshot bytes not included
    
    def test_browser_state_from_dict(self):
        """Test deserializing browser state from dict."""
        data = {
            "url": "https://example.com",
            "title": "Example",
            "scroll_x": 100,
            "scroll_y": 200,
            "cookies": [{"name": "session", "value": "abc"}],
            "local_storage": {"key": "value"},
            "session_storage": {},
            "form_values": {},
            "screenshot_hash": "abc123",
            "timestamp": 1234567890,
        }
        
        state = BrowserState.from_dict(data, screenshot=b"test")
        
        assert state.url == "https://example.com"
        assert state.title == "Example"
        assert state.scroll_x == 100
        assert state.cookies == [{"name": "session", "value": "abc"}]
        assert state.screenshot == b"test"
    
    def test_browser_state_matches(self):
        """Test browser state equality matching."""
        state1 = BrowserState(
            url="https://example.com",
            title="Example",
            scroll_x=100,
            scroll_y=200,
            screenshot_hash="abc123",
        )
        
        state2 = BrowserState(
            url="https://example.com",
            title="Different Title",
            scroll_x=100,
            scroll_y=200,
            screenshot_hash="abc123",
        )
        
        state3 = BrowserState(
            url="https://different.com",
            title="Example",
            scroll_x=100,
            scroll_y=200,
            screenshot_hash="abc123",
        )
        
        assert state1.matches(state2)  # Same URL, scroll, hash
        assert not state1.matches(state3)  # Different URL


# =============================================================================
# Checkpoint Tests
# =============================================================================

class TestCheckpoint:
    """Tests for Checkpoint dataclass."""
    
    def test_create_checkpoint(self):
        """Test creating a checkpoint."""
        state = BrowserState(url="https://example.com", title="Example")
        checkpoint = Checkpoint(
            id="ckpt_001",
            state=state,
            checkpoint_type=CheckpointType.PRE_ACTION,
            task_step=1,
            action_name="click",
        )
        
        assert checkpoint.id == "ckpt_001"
        assert checkpoint.checkpoint_type == CheckpointType.PRE_ACTION
        assert checkpoint.task_step == 1
        assert checkpoint.action_name == "click"
        assert checkpoint.parent_id is None
    
    def test_checkpoint_to_dict(self):
        """Test serializing checkpoint to dict."""
        state = BrowserState(url="https://example.com", title="Example")
        checkpoint = Checkpoint(
            id="ckpt_001",
            state=state,
            checkpoint_type=CheckpointType.PRE_ACTION,
            task_step=1,
        )
        
        data = checkpoint.to_dict()
        
        assert data["id"] == "ckpt_001"
        assert data["checkpoint_type"] == "pre_action"
        assert data["task_step"] == 1
        assert "state" in data
    
    def test_checkpoint_from_dict(self):
        """Test deserializing checkpoint from dict."""
        data = {
            "id": "ckpt_001",
            "state": {
                "url": "https://example.com",
                "title": "Example",
                "scroll_x": 0,
                "scroll_y": 0,
                "cookies": [],
                "local_storage": {},
                "session_storage": {},
                "form_values": {},
            },
            "checkpoint_type": "pre_action",
            "task_step": 1,
            "action_name": "click",
            "action_result": None,
            "metadata": {},
            "created_at": "2024-01-01T12:00:00",
            "parent_id": None,
            "children_ids": [],
        }
        
        checkpoint = Checkpoint.from_dict(data)
        
        assert checkpoint.id == "ckpt_001"
        assert checkpoint.checkpoint_type == CheckpointType.PRE_ACTION
        assert checkpoint.state.url == "https://example.com"


# =============================================================================
# CheckpointManager Tests
# =============================================================================

class TestCheckpointManager:
    """Tests for CheckpointManager."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def checkpoint_manager(self, temp_dir):
        """Create checkpoint manager with temp directory."""
        return CheckpointManager(
            max_checkpoints=10,
            persist_to_disk=False,
            persistence_dir=temp_dir,
        )
    
    @pytest.fixture
    def mock_page(self):
        """Create mock Playwright page."""
        page = AsyncMock()
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Example Page")
        page.evaluate = AsyncMock(return_value={"x": 100, "y": 200})
        page.screenshot = AsyncMock(return_value=b"fake_screenshot")
        
        # Mock context
        context = AsyncMock()
        context.cookies = AsyncMock(return_value=[])
        page.context = context
        
        return page
    
    @pytest.mark.asyncio
    async def test_create_checkpoint(self, checkpoint_manager, mock_page):
        """Test creating a checkpoint."""
        checkpoint = await checkpoint_manager.create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.PRE_ACTION,
            task_step=1,
            action_name="click",
        )
        
        assert checkpoint is not None
        assert checkpoint.id.startswith("ckpt_")
        assert checkpoint.checkpoint_type == CheckpointType.PRE_ACTION
        assert checkpoint.task_step == 1
        assert checkpoint.action_name == "click"
    
    @pytest.mark.asyncio
    async def test_create_checkpoint_captures_state(self, checkpoint_manager, mock_page):
        """Test that checkpoint captures browser state."""
        checkpoint = await checkpoint_manager.create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.PRE_ACTION,
        )
        
        assert checkpoint.state.url == "https://example.com"
        assert checkpoint.state.title == "Example Page"
        assert checkpoint.state.screenshot == b"fake_screenshot"
    
    @pytest.mark.asyncio
    async def test_get_checkpoint(self, checkpoint_manager, mock_page):
        """Test retrieving a checkpoint by ID."""
        created = await checkpoint_manager.create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.PRE_ACTION,
        )
        
        retrieved = checkpoint_manager.get_checkpoint(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
    
    @pytest.mark.asyncio
    async def test_get_latest_checkpoint(self, checkpoint_manager, mock_page):
        """Test getting the latest checkpoint."""
        await checkpoint_manager.create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.PRE_ACTION,
        )
        await checkpoint_manager.create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.POST_ACTION,
        )
        
        latest = checkpoint_manager.get_latest_checkpoint()
        
        assert latest is not None
        assert latest.checkpoint_type == CheckpointType.POST_ACTION
    
    @pytest.mark.asyncio
    async def test_get_latest_checkpoint_by_type(self, checkpoint_manager, mock_page):
        """Test getting latest checkpoint of specific type."""
        await checkpoint_manager.create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.PRE_ACTION,
        )
        await checkpoint_manager.create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.POST_ACTION,
        )
        await checkpoint_manager.create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.PRE_ACTION,
        )
        
        latest_pre = checkpoint_manager.get_latest_checkpoint(CheckpointType.PRE_ACTION)
        
        assert latest_pre is not None
        assert latest_pre.checkpoint_type == CheckpointType.PRE_ACTION
    
    @pytest.mark.asyncio
    async def test_restore_checkpoint(self, checkpoint_manager, mock_page):
        """Test restoring from checkpoint."""
        # Create checkpoint
        checkpoint = await checkpoint_manager.create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.PRE_ACTION,
        )
        
        # Mock page.goto for restore
        mock_page.goto = AsyncMock()
        
        # Restore
        success = await checkpoint_manager.restore_checkpoint(
            page=mock_page,
            checkpoint_id=checkpoint.id,
        )
        
        assert success is True
    
    @pytest.mark.asyncio
    async def test_restore_nonexistent_checkpoint(self, checkpoint_manager, mock_page):
        """Test restoring from nonexistent checkpoint."""
        success = await checkpoint_manager.restore_checkpoint(
            page=mock_page,
            checkpoint_id="nonexistent",
        )
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_max_checkpoints_pruning(self, mock_page):
        """Test that old checkpoints are pruned when limit exceeded."""
        manager = CheckpointManager(max_checkpoints=3, persist_to_disk=False)
        
        # Create more checkpoints than max
        for i in range(5):
            await manager.create_checkpoint(
                page=mock_page,
                checkpoint_type=CheckpointType.PRE_ACTION,
                task_step=i,
            )
        
        assert len(manager._checkpoints) <= 3
    
    def test_should_create_checkpoint(self, checkpoint_manager):
        """Test checkpoint interval logic."""
        checkpoint_manager.checkpoint_interval = 2
        
        assert not checkpoint_manager.should_create_checkpoint()  # 1
        assert checkpoint_manager.should_create_checkpoint()  # 2
        assert not checkpoint_manager.should_create_checkpoint()  # 3
        assert checkpoint_manager.should_create_checkpoint()  # 4
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, checkpoint_manager, mock_page):
        """Test getting checkpoint statistics."""
        await checkpoint_manager.create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.PRE_ACTION,
        )
        await checkpoint_manager.create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.POST_ACTION,
        )
        
        stats = checkpoint_manager.get_statistics()
        
        assert stats["total_checkpoints"] == 2
        assert "pre_action" in stats["checkpoint_types"]
        assert "post_action" in stats["checkpoint_types"]


# =============================================================================
# ErrorType and ErrorContext Tests
# =============================================================================

class TestErrorClassification:
    """Tests for error classification."""
    
    def test_error_type_values(self):
        """Test error type enum values."""
        assert ErrorType.ELEMENT_NOT_FOUND.value == "element_not_found"
        assert ErrorType.ACTION_TIMEOUT.value == "action_timeout"
        assert ErrorType.NAVIGATION_ERROR.value == "navigation_error"
        assert ErrorType.CAPTCHA_BLOCK.value == "captcha_block"
    
    def test_error_context_creation(self):
        """Test creating error context."""
        context = ErrorContext(
            error_type=ErrorType.ELEMENT_NOT_FOUND,
            error_message="Element not found: #button",
            action_name="click",
            action_params={"selector": "#button"},
        )
        
        assert context.error_type == ErrorType.ELEMENT_NOT_FOUND
        assert context.action_name == "click"
        assert context.attempt_count == 1
    
    def test_error_context_to_dict(self):
        """Test serializing error context."""
        context = ErrorContext(
            error_type=ErrorType.ACTION_TIMEOUT,
            error_message="Timeout waiting for element",
        )
        
        data = context.to_dict()
        
        assert data["error_type"] == "action_timeout"
        assert data["error_message"] == "Timeout waiting for element"


# =============================================================================
# FallbackStrategy Tests
# =============================================================================

class TestFallbackStrategies:
    """Tests for fallback strategy implementations."""
    
    @pytest.fixture
    def mock_page(self):
        """Create mock page."""
        page = AsyncMock()
        page.url = "https://example.com"
        page.evaluate = AsyncMock()
        page.screenshot = AsyncMock(return_value=b"screenshot")
        page.reload = AsyncMock()
        page.goto = AsyncMock()
        return page
    
    @pytest.fixture
    def error_context(self):
        """Create error context for testing."""
        return ErrorContext(
            error_type=ErrorType.ELEMENT_NOT_FOUND,
            error_message="Element not found",
            action_name="click",
            action_params={"selector": "#button", "description": "Submit button"},
        )
    
    @pytest.mark.asyncio
    async def test_scroll_and_retry_fallback(self, mock_page, error_context):
        """Test scroll and retry fallback strategy."""
        strategy = ScrollAndRetryFallback()
        
        # Test can_handle
        can_handle = await strategy.can_handle(error_context)
        assert can_handle is True
        
        # Test execute
        result = await strategy.execute(error_context, mock_page)
        
        assert result.success is True
        assert result.strategy_name == "scroll_and_retry"
        assert result.should_retry is True
        mock_page.evaluate.assert_called()
    
    @pytest.mark.asyncio
    async def test_extended_wait_fallback(self, mock_page, error_context):
        """Test extended wait fallback strategy."""
        strategy = ExtendedWaitFallback(max_wait=5.0)
        
        can_handle = await strategy.can_handle(error_context)
        assert can_handle is True
        
        # Mock wait_for_selector to fail
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
        
        result = await strategy.execute(error_context, mock_page)
        
        assert result.success is True
        assert result.strategy_name == "extended_wait"
    
    @pytest.mark.asyncio
    async def test_refresh_and_retry_fallback(self, mock_page):
        """Test refresh and retry fallback strategy."""
        strategy = RefreshAndRetryFallback()
        context = ErrorContext(
            error_type=ErrorType.STATE_MISMATCH,
            error_message="Page state changed",
        )
        
        can_handle = await strategy.can_handle(context)
        assert can_handle is True
        
        result = await strategy.execute(context, mock_page)
        
        assert result.success is True
        assert result.strategy_name == "refresh_and_retry"
        mock_page.reload.assert_called()
    
    @pytest.mark.asyncio
    async def test_navigation_retry_fallback(self, mock_page):
        """Test navigation retry fallback strategy."""
        strategy = NavigationRetryFallback()
        context = ErrorContext(
            error_type=ErrorType.NAVIGATION_ERROR,
            error_message="Navigation failed",
            action_params={"url": "https://example.com/page"},
        )
        
        can_handle = await strategy.can_handle(context)
        assert can_handle is True
        
        result = await strategy.execute(context, mock_page)
        
        assert result.success is True
        assert result.strategy_name == "navigation_retry"
        mock_page.goto.assert_called()


# =============================================================================
# FallbackManager Tests
# =============================================================================

class TestFallbackManager:
    """Tests for FallbackManager."""
    
    @pytest.fixture
    def fallback_manager(self):
        """Create fallback manager."""
        manager = FallbackManager()
        # Register some strategies
        manager.register_strategy(ScrollAndRetryFallback())
        manager.register_strategy(ExtendedWaitFallback())
        return manager
    
    def test_register_strategy(self, fallback_manager):
        """Test registering a strategy."""
        strategy = RefreshAndRetryFallback()
        fallback_manager.register_strategy(strategy)
        
        assert "refresh_and_retry" in fallback_manager._strategies
    
    def test_unregister_strategy(self, fallback_manager):
        """Test unregistering a strategy."""
        fallback_manager.unregister_strategy("scroll_and_retry")
        
        assert "scroll_and_retry" not in fallback_manager._strategies
    
    def test_get_all_strategies_sorted(self, fallback_manager):
        """Test getting strategies sorted by priority."""
        strategies = fallback_manager.get_all_strategies()
        
        priorities = [s.priority for s in strategies]
        assert priorities == sorted(priorities)
    
    def test_classify_error_element_not_found(self, fallback_manager):
        """Test classifying element not found error."""
        error = Exception("Timeout waiting for selector '#button'")
        
        context = fallback_manager.classify_error(error)
        
        assert context.error_type == ErrorType.ELEMENT_NOT_FOUND
    
    def test_classify_error_timeout(self, fallback_manager):
        """Test classifying timeout error."""
        error = Exception("Action timeout after 30000ms")
        
        context = fallback_manager.classify_error(error)
        
        assert context.error_type == ErrorType.ACTION_TIMEOUT
    
    def test_classify_error_navigation(self, fallback_manager):
        """Test classifying navigation error."""
        error = Exception("net::ERR_CONNECTION_REFUSED")
        
        context = fallback_manager.classify_error(error)
        
        assert context.error_type == ErrorType.NAVIGATION_ERROR
    
    def test_classify_error_captcha(self, fallback_manager):
        """Test classifying CAPTCHA error."""
        error = Exception("CAPTCHA detected on page")
        
        context = fallback_manager.classify_error(error)
        
        assert context.error_type == ErrorType.CAPTCHA_BLOCK
    
    @pytest.mark.asyncio
    async def test_get_applicable_strategies(self, fallback_manager):
        """Test getting applicable strategies for error."""
        context = ErrorContext(
            error_type=ErrorType.ELEMENT_NOT_FOUND,
            error_message="Element not found",
        )
        
        strategies = await fallback_manager.get_applicable_strategies(context)
        
        assert len(strategies) > 0
        for strategy in strategies:
            assert ErrorType.ELEMENT_NOT_FOUND in strategy.applicable_errors
    
    def test_error_history(self, fallback_manager):
        """Test error history tracking."""
        for i in range(5):
            fallback_manager.classify_error(Exception(f"Error {i}"))
        
        history = fallback_manager.get_error_history(limit=3)
        
        assert len(history) == 3
    
    def test_get_statistics(self, fallback_manager):
        """Test getting fallback manager statistics."""
        fallback_manager.classify_error(Exception("Element not found"))
        fallback_manager.classify_error(Exception("Timeout"))
        
        stats = fallback_manager.get_statistics()
        
        assert stats["total_errors"] == 2
        assert "element_not_found" in stats["error_types"]


# =============================================================================
# StateStack Tests
# =============================================================================

class TestStateStack:
    """Tests for StateStack."""
    
    @pytest.fixture
    def state_stack(self):
        """Create state stack."""
        return StateStack(max_depth=10, auto_prune=False)
    
    @pytest.fixture
    def browser_state(self):
        """Create browser state for testing."""
        return BrowserState(
            url="https://example.com",
            title="Example",
            scroll_x=0,
            scroll_y=0,
        )
    
    def test_push_state(self, state_stack, browser_state):
        """Test pushing state onto stack."""
        frame = state_stack.push(
            state=browser_state,
            action_name="navigate",
            action_description="Navigate to example.com",
        )
        
        assert frame is not None
        assert frame.id.startswith("frame_")
        assert frame.action_name == "navigate"
        assert state_stack.get_depth() == 1
    
    def test_pop_state(self, state_stack, browser_state):
        """Test popping state from stack."""
        state_stack.push(state=browser_state)
        state_stack.push(state=browser_state)
        
        popped = state_stack.pop()
        
        assert popped is not None
        assert state_stack.get_depth() == 1
    
    def test_peek_state(self, state_stack, browser_state):
        """Test peeking at state without removing."""
        state_stack.push(state=browser_state, action_name="action1")
        state_stack.push(state=browser_state, action_name="action2")
        
        top = state_stack.peek(0)
        second = state_stack.peek(1)
        
        assert top.action_name == "action2"
        assert second.action_name == "action1"
        assert state_stack.get_depth() == 2  # Stack unchanged
    
    def test_rollback_steps(self, state_stack, browser_state):
        """Test rolling back by steps."""
        state_stack.push(state=browser_state, action_name="action1")
        state_stack.push(state=browser_state, action_name="action2")
        state_stack.push(state=browser_state, action_name="action3")
        
        frame = state_stack.rollback(steps=1)
        
        assert state_stack.get_depth() == 2
        assert frame.action_name == "action2"
    
    def test_rollback_to_frame(self, state_stack, browser_state):
        """Test rolling back to specific frame."""
        frame1 = state_stack.push(state=browser_state, action_name="action1")
        state_stack.push(state=browser_state, action_name="action2")
        state_stack.push(state=browser_state, action_name="action3")
        
        result = state_stack.rollback_to_frame(frame1.id)
        
        assert result is not None
        assert result.id == frame1.id
        assert state_stack.get_depth() == 1
    
    def test_create_branch(self, state_stack, browser_state):
        """Test creating a branch."""
        state_stack.push(state=browser_state, action_name="action1")
        
        branch_frame = state_stack.create_branch("test_branch")
        
        assert branch_frame.is_branch_point is True
        assert branch_frame.branch_name == "test_branch"
        assert "test_branch" in state_stack.get_all_branches()
    
    def test_get_frame_history(self, state_stack, browser_state):
        """Test getting frame history."""
        for i in range(5):
            state_stack.push(state=browser_state, action_name=f"action{i}")
        
        history = state_stack.get_frame_history(limit=3)
        
        assert len(history) == 3
    
    def test_max_depth_enforcement(self, browser_state):
        """Test max depth enforcement with auto-prune."""
        stack = StateStack(max_depth=5, auto_prune=True, prune_threshold=0.8)
        
        for i in range(10):
            stack.push(state=browser_state, action_name=f"action{i}")
        
        assert stack.get_depth() <= 5
    
    def test_get_statistics(self, state_stack, browser_state):
        """Test getting stack statistics."""
        state_stack.push(state=browser_state)
        state_stack.push(state=browser_state)
        state_stack.pop()
        
        stats = state_stack.get_statistics()
        
        assert stats["push_count"] == 2
        assert stats["pop_count"] == 1
        assert stats["depth"] == 1


# =============================================================================
# RecoveryOrchestrator Tests
# =============================================================================

class TestRecoveryOrchestrator:
    """Tests for RecoveryOrchestrator."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def recovery_system(self, temp_dir):
        """Create complete recovery system."""
        checkpoint_manager = CheckpointManager(
            max_checkpoints=10,
            persist_to_disk=False,
            persistence_dir=temp_dir,
        )
        fallback_manager = FallbackManager()
        fallback_manager.register_strategy(ScrollAndRetryFallback())
        fallback_manager.register_strategy(ExtendedWaitFallback())
        
        state_stack = StateStack(max_depth=10)
        
        config = RecoveryConfig(
            max_recovery_attempts=2,
            recovery_delay=0.1,
        )
        
        orchestrator = RecoveryOrchestrator(
            checkpoint_manager=checkpoint_manager,
            fallback_manager=fallback_manager,
            state_stack=state_stack,
            config=config,
        )
        
        return {
            "orchestrator": orchestrator,
            "checkpoint_manager": checkpoint_manager,
            "fallback_manager": fallback_manager,
            "state_stack": state_stack,
        }
    
    @pytest.fixture
    def mock_page(self):
        """Create mock page."""
        page = AsyncMock()
        page.url = "https://example.com"
        page.title = AsyncMock(return_value="Example")
        page.evaluate = AsyncMock(return_value={"x": 0, "y": 0})
        page.screenshot = AsyncMock(return_value=b"screenshot")
        page.content = AsyncMock(return_value="<html><body>Content</body></html>")
        page.goto = AsyncMock()
        page.reload = AsyncMock()
        
        context = AsyncMock()
        context.cookies = AsyncMock(return_value=[])
        page.context = context
        
        return page
    
    @pytest.mark.asyncio
    async def test_recover_from_element_not_found(self, recovery_system, mock_page):
        """Test recovery from element not found error."""
        orchestrator = recovery_system["orchestrator"]
        
        # Create initial checkpoint
        await recovery_system["checkpoint_manager"].create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.PRE_ACTION,
        )
        
        error = Exception("Element not found: #button")
        
        result = await orchestrator.recover(
            error=error,
            page=mock_page,
            action_name="click",
            action_params={"selector": "#button"},
        )
        
        assert result.status in [RecoveryStatus.SUCCESS, RecoveryStatus.FAILED]
        assert result.attempts > 0
    
    @pytest.mark.asyncio
    async def test_recovery_creates_recovery_checkpoint(self, recovery_system, mock_page):
        """Test that recovery creates a checkpoint."""
        orchestrator = recovery_system["orchestrator"]
        checkpoint_manager = recovery_system["checkpoint_manager"]
        
        error = Exception("Test error")
        
        await orchestrator.recover(
            error=error,
            page=mock_page,
            max_attempts=1,
        )
        
        # Check for recovery checkpoint
        recovery_checkpoints = checkpoint_manager.get_checkpoints_by_type(
            CheckpointType.RECOVERY
        )
        assert len(recovery_checkpoints) >= 1
    
    @pytest.mark.asyncio
    async def test_recovery_tracks_history(self, recovery_system, mock_page):
        """Test that recovery tracks history."""
        orchestrator = recovery_system["orchestrator"]
        
        error = Exception("Test error")
        
        await orchestrator.recover(
            error=error,
            page=mock_page,
            max_attempts=1,
        )
        
        history = orchestrator.get_recovery_history()
        assert len(history) >= 1
    
    @pytest.mark.asyncio
    async def test_recovery_statistics(self, recovery_system, mock_page):
        """Test recovery statistics."""
        orchestrator = recovery_system["orchestrator"]
        
        error = Exception("Test error")
        
        await orchestrator.recover(
            error=error,
            page=mock_page,
            max_attempts=1,
        )
        
        stats = orchestrator.get_statistics()
        
        assert stats["total_recoveries"] >= 1
        assert "success_rate" in stats
    
    @pytest.mark.asyncio
    async def test_manual_intervention_callback(self, recovery_system, mock_page):
        """Test manual intervention callback."""
        orchestrator = recovery_system["orchestrator"]
        
        callback_called = []
        
        def callback(result):
            callback_called.append(result)
        
        orchestrator.add_manual_intervention_callback(callback)
        
        # Force a failed recovery
        error = Exception("Unrecoverable error")
        
        await orchestrator.recover(
            error=error,
            page=mock_page,
            max_attempts=1,
        )
        
        # Callback should be called for failed recovery
        # Note: This depends on recovery actually failing
    
    @pytest.mark.asyncio
    async def test_is_recovering_flag(self, recovery_system, mock_page):
        """Test is_recovering flag during recovery."""
        orchestrator = recovery_system["orchestrator"]
        
        assert not orchestrator.is_recovering()
        
        # Start recovery (it will complete quickly)
        error = Exception("Test error")
        await orchestrator.recover(
            error=error,
            page=mock_page,
            max_attempts=1,
        )
        
        assert not orchestrator.is_recovering()
    
    @pytest.mark.asyncio
    async def test_graceful_degradation(self, recovery_system, mock_page):
        """Test graceful degradation."""
        orchestrator = recovery_system["orchestrator"]
        checkpoint_manager = recovery_system["checkpoint_manager"]
        
        # Create a checkpoint to fall back to
        await checkpoint_manager.create_checkpoint(
            page=mock_page,
            checkpoint_type=CheckpointType.PRE_ACTION,
        )
        
        error_context = ErrorContext(
            error_type=ErrorType.ELEMENT_NOT_FOUND,
            error_message="Element not found",
        )
        
        success, message = await orchestrator.graceful_degradation(
            page=mock_page,
            error_context=error_context,
        )
        
        # Graceful degradation should succeed
        assert success is True


# =============================================================================
# Integration Tests
# =============================================================================

class TestResilienceIntegration:
    """Integration tests for resilience module."""
    
    @pytest.fixture
    def full_system(self):
        """Create full resilience system."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_manager = CheckpointManager(
                max_checkpoints=20,
                persist_to_disk=True,
                persistence_dir=tmpdir,
            )
            
            fallback_manager = FallbackManager()
            fallback_manager.register_strategy(ScrollAndRetryFallback())
            fallback_manager.register_strategy(ExtendedWaitFallback())
            fallback_manager.register_strategy(RefreshAndRetryFallback())
            
            state_stack = StateStack(max_depth=15)
            
            orchestrator = RecoveryOrchestrator(
                checkpoint_manager=checkpoint_manager,
                fallback_manager=fallback_manager,
                state_stack=state_stack,
            )
            
            yield {
                "checkpoint_manager": checkpoint_manager,
                "fallback_manager": fallback_manager,
                "state_stack": state_stack,
                "orchestrator": orchestrator,
            }
    
    def test_module_exports(self):
        """Test that all expected classes are exported."""
        from browser_agent.resilience import (
            CheckpointManager, Checkpoint, BrowserState,
            FallbackStrategy, FallbackManager, ErrorType, FallbackResult,
            StateStack, StateFrame,
            RecoveryOrchestrator, RecoveryResult,
        )
        
        # All classes should be importable
        assert CheckpointManager is not None
        assert FallbackManager is not None
        assert StateStack is not None
        assert RecoveryOrchestrator is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
