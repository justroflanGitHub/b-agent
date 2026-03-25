"""
LLM Client - OpenAI-compatible client for LM Studio and other providers.

This module provides:
- Async chat completions
- Vision model support
- Streaming responses
- Retry logic with exponential backoff
"""

import asyncio
import base64
import json
import logging
import time
from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from dataclasses import dataclass
from enum import Enum

import aiohttp

from ..config import Config, LLMConfig

logger = logging.getLogger(__name__)


class MessageRole(Enum):
    """Chat message roles."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ChatMessage:
    """Chat message structure."""
    role: MessageRole
    content: str
    images: Optional[List[str]] = None  # Base64 encoded images
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        msg = {
            "role": self.role.value,
            "content": self.content
        }
        if self.images:
            msg["images"] = self.images
        return msg


@dataclass
class ChatResponse:
    """Chat completion response."""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str
    latency_ms: float


class LLMClient:
    """
    OpenAI-compatible LLM client with retry logic.
    
    Supports:
    - LM Studio (local)
    - Ollama (local)
    - OpenAI (cloud)
    - Any OpenAI-compatible API
    
    Usage:
        client = LLMClient(config)
        response = await client.chat([
            ChatMessage(MessageRole.USER, "Hello!")
        ])
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.llm_config = self.config.llm
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._request_count = 0
        self._total_latency = 0.0
    
    async def __aenter__(self):
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.llm_config.timeout + 10)
            self._session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    @property
    def api_url(self) -> str:
        """Get the API base URL."""
        return self.llm_config.base_url.rstrip("/")
    
    @property
    def chat_endpoint(self) -> str:
        """Get the chat completions endpoint."""
        return f"{self.api_url}/v1/chat/completions"
    
    async def chat(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatResponse:
        """
        Send chat completion request.
        
        Args:
            messages: List of chat messages
            system_prompt: Optional system prompt to prepend
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            ChatResponse with content and metadata
        """
        await self._ensure_session()
        
        # Build message list
        api_messages = []
        if system_prompt:
            api_messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        for msg in messages:
            api_messages.append(msg.to_dict())
        
        # Build payload
        payload = {
            "model": self.llm_config.model,
            "messages": api_messages,
            "temperature": temperature or self.llm_config.temperature,
            "max_tokens": max_tokens or self.llm_config.max_tokens,
        }
        
        # Add any extra parameters
        payload.update(kwargs)
        
        # Execute with retry
        return await self._execute_with_retry(payload)
    
    async def chat_with_image(
        self,
        text: str,
        image: Union[bytes, str],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ChatResponse:
        """
        Send chat with image for vision models.
        
        Args:
            text: Text prompt
            image: Image bytes or base64 string
            system_prompt: Optional system prompt
            
        Returns:
            ChatResponse from vision model
        """
        # Encode image if needed
        if isinstance(image, bytes):
            image_b64 = base64.b64encode(image).decode("utf-8")
        else:
            image_b64 = image
        
        message = ChatMessage(
            role=MessageRole.USER,
            content=text,
            images=[image_b64]
        )
        
        return await self.chat([message], system_prompt=system_prompt, **kwargs)
    
    async def chat_stream(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion response.
        
        Yields:
            Text chunks as they arrive
        """
        await self._ensure_session()
        
        # Build message list
        api_messages = []
        if system_prompt:
            api_messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        for msg in messages:
            api_messages.append(msg.to_dict())
        
        payload = {
            "model": self.llm_config.model,
            "messages": api_messages,
            "temperature": self.llm_config.temperature,
            "max_tokens": self.llm_config.max_tokens,
            "stream": True,
        }
        payload.update(kwargs)
        
        start_time = time.time()
        
        try:
            async with self._session.post(
                self.chat_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API error {response.status}: {error_text}")
                
                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if not line or line == "data: [DONE]":
                        continue
                    
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data.get("choices"):
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise
        
        latency = (time.time() - start_time) * 1000
        logger.debug(f"Stream completed in {latency:.0f}ms")
    
    async def _execute_with_retry(self, payload: Dict) -> ChatResponse:
        """Execute request with exponential backoff retry."""
        max_retries = self.llm_config.retries
        base_delay = self.config.resilience.exponential_backoff_base
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await self._execute_request(payload)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"LLM request failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
        
        raise Exception(f"LLM request failed after {max_retries} attempts: {last_error}")
    
    async def _execute_request(self, payload: Dict) -> ChatResponse:
        """Execute single API request."""
        start_time = time.time()
        
        try:
            async with self._session.post(
                self.chat_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                latency = (time.time() - start_time) * 1000
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API error {response.status}: {error_text}")
                
                data = await response.json()
                
                if not data.get("choices"):
                    raise Exception("No choices in response")
                
                choice = data["choices"][0]
                content = choice.get("message", {}).get("content", "")
                
                self._request_count += 1
                self._total_latency += latency
                
                return ChatResponse(
                    content=content,
                    model=data.get("model", self.llm_config.model),
                    usage=data.get("usage", {}),
                    finish_reason=choice.get("finish_reason", "stop"),
                    latency_ms=latency
                )
                
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "request_count": self._request_count,
            "total_latency_ms": self._total_latency,
            "avg_latency_ms": self._total_latency / max(1, self._request_count)
        }


class VisionClient(LLMClient):
    """
    Specialized client for vision models (UI-TARS, etc.).
    
    Provides convenience methods for:
    - Screenshot analysis
    - Element detection
    - Action prediction
    """
    
    async def analyze_screenshot(
        self,
        screenshot: bytes,
        prompt: str,
        **kwargs
    ) -> ChatResponse:
        """
        Analyze screenshot with custom prompt.
        
        Args:
            screenshot: PNG screenshot bytes
            prompt: Analysis prompt
            
        Returns:
            ChatResponse with analysis
        """
        return await self.chat_with_image(prompt, screenshot, **kwargs)
    
    async def detect_elements(
        self,
        screenshot: bytes,
        element_types: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Detect UI elements in screenshot.
        
        Args:
            screenshot: PNG screenshot bytes
            element_types: Types to detect (button, input, link, etc.)
            
        Returns:
            Dict with detected elements
        """
        element_list = element_types or ["button", "input", "link", "text field", "dropdown"]
        
        prompt = f"""Analyze this screenshot and detect all interactive elements.

Look for these element types: {', '.join(element_list)}

For each element found, provide:
- type: The element type
- text: Any visible text on/around the element
- bbox: Bounding box as [x1, y1, x2, y2]
- confidence: Detection confidence (0-1)

Return as JSON:
{{
    "elements": [
        {{"type": "button", "text": "Submit", "bbox": [100, 200, 150, 230], "confidence": 0.95}}
    ]
}}
"""
        
        response = await self.chat_with_image(prompt, screenshot, **kwargs)
        
        # Parse JSON from response
        try:
            content = response.content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
        except json.JSONDecodeError:
            pass
        
        return {"elements": [], "raw_response": response.content}
    
    async def predict_action(
        self,
        screenshot: bytes,
        task: str,
        available_actions: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Predict next action based on visual state and task.
        
        Args:
            screenshot: Current page screenshot
            task: Task description
            available_actions: List of available actions
            
        Returns:
            Dict with predicted action
        """
        actions = available_actions or ["click", "type", "scroll", "select", "press_enter"]
        
        prompt = f"""Task: {task}

Analyze the current screenshot and determine the next action to accomplish this task.

Available actions: {', '.join(actions)}

Return as JSON:
{{
    "action": {{
        "type": "click|type|scroll|select|press_enter",
        "x": coordinate_x,
        "y": coordinate_y,
        "text": "text to type (if applicable)",
        "description": "What this action does"
    }},
    "reasoning": "Why this action was chosen",
    "confidence": 0.0-1.0
}}

Screenshot dimensions: 2560x1440
"""
        
        response = await self.chat_with_image(prompt, screenshot, **kwargs)
        
        # Parse JSON from response
        try:
            content = response.content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
        except json.JSONDecodeError:
            pass
        
        return {"action": None, "raw_response": response.content}
    
    async def get_click_coordinates(
        self,
        screenshot: bytes,
        element_description: str,
        viewport_width: int = 2560,
        viewport_height: int = 1440,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get precise click coordinates for an element using tool-calling.
        
        This is a dedicated tool for coordinate calculation, separate from
        the main action planning prompt.
        
        Args:
            screenshot: PNG screenshot bytes
            element_description: Description of element to click
            viewport_width: Screenshot width in pixels
            viewport_height: Screenshot height in pixels
            
        Returns:
            Dict with x, y coordinates and confidence
        """
        prompt = f"""You are a precise coordinate detection tool. Analyze the screenshot and find the exact center coordinates for: "{element_description}"

SCREENSHOT DIMENSIONS: {viewport_width}x{viewport_height} (width x height)

CRITICAL COORDINATE RULES:
1. Look at the screenshot CAREFULLY and identify the EXACT pixel coordinates
2. Coordinates must be within the screenshot bounds:
   - X: 0 to {viewport_width}
   - Y: 0 to {viewport_height}

IMPORTANT FOR GOOGLE.COM:
- The search bar is CENTERED horizontally around X: {viewport_width // 2}
- Google.com search field coordinates: x=xxxx, y=yyy
- Google.com search field coordinates is around X=1280, y=650
- Look for the actual search box position
- Provide REAL coordinates based on what you see in the screenshot. Don't use generic coordinates.
- if user uses dark mode, the search bar is lighter, if user uses light mode, the search bar is darker

Return JSON with the center coordinates:
{{
    "x": <integer x coordinate>,
    "y": <integer y coordinate>,
    "confidence": <float 0.0-1.0>,
    "element_found": <boolean>,
    "notes": "<optional notes about the element>"
}}
"""
        
        response = await self.chat_with_image(prompt, screenshot, **kwargs)
        
        # Parse JSON from response
        try:
            content = response.content
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(content[json_start:json_end])
                logger.info(f"🎯 Coordinate tool: ({result.get('x')}, {result.get('y')}) confidence={result.get('confidence', 0)}")
                return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse coordinate response: {e}")
        
        return {"x": 0, "y": 0, "confidence": 0, "element_found": False, "error": "Failed to parse response"}


# Convenience functions
async def create_client(config: Optional[Config] = None) -> LLMClient:
    """Create and initialize an LLM client."""
    client = LLMClient(config)
    await client._ensure_session()
    return client


async def create_vision_client(config: Optional[Config] = None) -> VisionClient:
    """Create and initialize a vision client."""
    client = VisionClient(config)
    await client._ensure_session()
    return client
