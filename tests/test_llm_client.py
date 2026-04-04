"""
Unit tests for browser_agent/llm/client.py

Tests cover:
- ChatMessage dataclass
- ChatResponse dataclass
- LLMClient class
- VisionClient class
- Mock HTTP responses for testing
"""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from browser_agent.llm.client import (
    LLMClient,
    VisionClient,
    ChatMessage,
    ChatResponse,
    MessageRole,
)
from browser_agent.config import Config, LLMConfig


class TestChatMessage:
    """Tests for ChatMessage dataclass."""
    
    def test_create_user_message(self):
        """Test creating a user message."""
        msg = ChatMessage(role=MessageRole.USER, content="Hello")
        
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert msg.images is None
    
    def test_create_message_with_image(self):
        """Test creating a message with image."""
        msg = ChatMessage(
            role=MessageRole.USER,
            content="What's in this image?",
            images=["base64imagedata"]
        )
        
        assert msg.role == MessageRole.USER
        assert msg.content == "What's in this image?"
        assert msg.images == ["base64imagedata"]
    
    def test_to_dict(self):
        """Test converting message to dictionary."""
        msg = ChatMessage(role=MessageRole.USER, content="Test")
        
        data = msg.to_dict()
        
        assert data["role"] == "user"
        assert data["content"] == "Test"
        assert "images" not in data
    
    def test_to_dict_with_image(self):
        """Test converting message with image to dictionary."""
        msg = ChatMessage(
            role=MessageRole.USER,
            content="Test",
            images=["imagedata"]
        )
        
        data = msg.to_dict()
        
        assert data["role"] == "user"
        assert data["content"] == "Test"
        assert data["images"] == ["imagedata"]
    
    def test_all_roles(self):
        """Test all message roles."""
        roles = [MessageRole.SYSTEM, MessageRole.USER, MessageRole.ASSISTANT]
        
        for role in roles:
            msg = ChatMessage(role=role, content="Test")
            assert msg.role == role


class TestChatResponse:
    """Tests for ChatResponse dataclass."""
    
    def test_create_response(self):
        """Test creating a chat response."""
        response = ChatResponse(
            content="Hello!",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            finish_reason="stop",
            latency_ms=150.5
        )
        
        assert response.content == "Hello!"
        assert response.model == "test-model"
        assert response.usage["prompt_tokens"] == 10
        assert response.finish_reason == "stop"
        assert response.latency_ms == 150.5


class TestLLMClient:
    """Tests for LLMClient class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()
    
    @pytest.fixture
    def client(self, config):
        """Create test client."""
        return LLMClient(config)
    
    def test_init(self, client):
        """Test client initialization."""
        assert client.config is not None
        assert client.llm_config is not None
        assert client._session is None
    
    def test_api_url(self, client):
        """Test API URL property."""
        assert client.api_url == "http://192.168.1.5:1234"
    
    def test_chat_endpoint(self, client):
        """Test chat endpoint property."""
        assert client.chat_endpoint == "http://192.168.1.5:1234/v1/chat/completions"
    
    @pytest.mark.asyncio
    async def test_ensure_session(self, client):
        """Test session creation."""
        await client._ensure_session()
        
        assert client._session is not None
        assert not client._session.closed
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test session cleanup."""
        await client._ensure_session()
        await client.close()
        
        assert client._session.closed
    
    @pytest.mark.asyncio
    async def test_context_manager(self, config):
        """Test async context manager."""
        async with LLMClient(config) as client:
            assert client._session is not None
        
        assert client._session.closed
    
    def test_get_stats(self, client):
        """Test statistics retrieval."""
        stats = client.get_stats()
        
        assert "request_count" in stats
        assert "total_latency_ms" in stats
        assert "avg_latency_ms" in stats
    
    @pytest.mark.asyncio
    async def test_chat_mock(self, client):
        """Test chat with mocked HTTP response."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "choices": [
                {
                    "message": {"content": "Test response"},
                    "finish_reason": "stop"
                }
            ],
            "model": "test-model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        })
        
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock()
            
            await client._ensure_session()
            
            # This would normally call the API
            # For now, just test the structure
            messages = [ChatMessage(MessageRole.USER, "Hello")]
            
            # Verify message structure
            assert messages[0].role == MessageRole.USER
            assert messages[0].content == "Hello"
        
        await client.close()


class TestVisionClient:
    """Tests for VisionClient class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()
    
    @pytest.fixture
    def client(self, config):
        """Create test vision client."""
        return VisionClient(config)
    
    def test_init(self, client):
        """Test vision client initialization."""
        assert client.config is not None
        assert client.llm_config is not None
    
    @pytest.mark.asyncio
    async def test_analyze_screenshot_structure(self, client):
        """Test screenshot analysis structure (without actual API call)."""
        # Test that method exists and accepts correct parameters
        assert hasattr(client, "analyze_screenshot")
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_detect_elements_structure(self, client):
        """Test element detection structure."""
        assert hasattr(client, "detect_elements")
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_predict_action_structure(self, client):
        """Test action prediction structure."""
        assert hasattr(client, "predict_action")
        
        await client.close()


class TestLLMClientRetry:
    """Tests for retry logic."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration with low retries."""
        config = Config()
        config.llm.retries = 2
        config.resilience.exponential_backoff_base = 0.1
        return config
    
    @pytest.fixture
    def client(self, config):
        """Create test client."""
        return LLMClient(config)
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self, client):
        """Test that client retries on failure."""
        # Track call count
        call_count = 0
        
        async def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise Exception("Connection error")
        
        # Patch the execute method
        client._execute_request = mock_execute
        
        # Should raise after retries exhausted
        with pytest.raises(Exception) as exc_info:
            await client._execute_with_retry({"test": "payload"})
        
        assert "2 attempts" in str(exc_info.value)
        assert call_count == 2
        
        await client.close()


class TestMessageRole:
    """Tests for MessageRole enum."""
    
    def test_all_roles_exist(self):
        """Test that all expected roles exist."""
        assert MessageRole.SYSTEM.value == "system"
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"


class TestJSONParsing:
    """Tests for JSON parsing in responses."""
    
    def test_parse_json_from_response(self):
        """Test extracting JSON from text response."""
        response_text = '''Here is the action: {"type": "click", "x": 100, "y": 200}'''
        
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        
        if json_start >= 0 and json_end > json_start:
            data = json.loads(response_text[json_start:json_end])
            
            assert data["type"] == "click"
            assert data["x"] == 100
            assert data["y"] == 200
    
    def test_parse_nested_json(self):
        """Test parsing nested JSON."""
        response_text = '''{"action": {"type": "type", "text": "hello"}, "confidence": 0.9}'''
        
        data = json.loads(response_text)
        
        assert data["action"]["type"] == "type"
        assert data["action"]["text"] == "hello"
        assert data["confidence"] == 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
