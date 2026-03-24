"""
Tests for Phase 2: Visual Intelligence Module.

Tests:
- VisualAnalyzer: Page analysis, element detection
- VisualDiff: Screenshot comparison
- VisionCache: Caching functionality
- Visual actions: hover_visual, type_visual
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import base64

from browser_agent.vision.analyzer import (
    VisualAnalyzer,
    BoundingBox,
    ElementInfo,
    PageState,
    ElementType,
    PageAnalysis,
)
from browser_agent.vision.diff import VisualDiff, DiffRegion, VisualDiffResult
from browser_agent.vision.cache import VisionCache, CacheEntry
from browser_agent.actor.actions import ActionType


# ==================== BoundingBox Tests ====================

class TestBoundingBox:
    """Tests for BoundingBox dataclass."""
    
    def test_bounding_box_creation(self):
        """Test creating a bounding box."""
        bbox = BoundingBox(x=100, y=200, width=50, height=30)
        assert bbox.x == 100
        assert bbox.y == 200
        assert bbox.width == 50
        assert bbox.height == 30
        assert bbox.confidence == 1.0
    
    def test_bounding_box_center(self):
        """Test getting center coordinates."""
        bbox = BoundingBox(x=100, y=200, width=50, height=30)
        center = bbox.center
        assert center == (125, 215)
    
    def test_bounding_box_area(self):
        """Test area calculation."""
        bbox = BoundingBox(x=0, y=0, width=100, height=50)
        assert bbox.area == 5000
    
    def test_bounding_box_contains(self):
        """Test point containment."""
        bbox = BoundingBox(x=100, y=100, width=50, height=50)
        assert bbox.contains(125, 125)  # Inside
        assert bbox.contains(100, 100)  # Corner
        assert not bbox.contains(50, 50)  # Outside
        assert not bbox.contains(200, 200)  # Outside
    
    def test_bounding_box_overlaps(self):
        """Test overlap detection."""
        bbox1 = BoundingBox(x=0, y=0, width=100, height=100)
        bbox2 = BoundingBox(x=50, y=50, width=100, height=100)  # Overlaps
        bbox3 = BoundingBox(x=200, y=200, width=50, height=50)  # No overlap
        
        assert bbox1.overlaps(bbox2)
        assert not bbox1.overlaps(bbox3)
    
    def test_bounding_box_to_dict(self):
        """Test serialization."""
        bbox = BoundingBox(x=10, y=20, width=30, height=40, confidence=0.9)
        d = bbox.to_dict()
        
        assert d["x"] == 10
        assert d["y"] == 20
        assert d["width"] == 30
        assert d["height"] == 40
        assert d["confidence"] == 0.9
        assert d["center"] == (25, 40)


# ==================== ElementInfo Tests ====================

class TestElementInfo:
    """Tests for ElementInfo dataclass."""
    
    def test_element_info_creation(self):
        """Test creating element info."""
        bbox = BoundingBox(x=0, y=0, width=100, height=50)
        elem = ElementInfo(
            bounding_box=bbox,
            element_type=ElementType.BUTTON,
            description="Submit button",
            is_clickable=True
        )
        
        assert elem.element_type == ElementType.BUTTON
        assert elem.description == "Submit button"
        assert elem.is_clickable is True
        assert elem.is_visible is True
    
    def test_element_info_to_dict(self):
        """Test element info serialization."""
        bbox = BoundingBox(x=0, y=0, width=100, height=50)
        elem = ElementInfo(
            bounding_box=bbox,
            element_type=ElementType.INPUT_TEXT,
            description="Email input",
            text_content="Enter email",
            is_typeable=True
        )
        
        d = elem.to_dict()
        assert d["element_type"] == "input_text"
        assert d["description"] == "Email input"
        assert d["text_content"] == "Enter email"
        assert d["is_typeable"] is True


# ==================== PageState Tests ====================

class TestPageState:
    """Tests for PageState enum."""
    
    def test_page_state_values(self):
        """Test page state enum values."""
        assert PageState.READY.value == "ready"
        assert PageState.LOADING.value == "loading"
        assert PageState.ERROR.value == "error"
        assert PageState.MODAL.value == "modal"
        assert PageState.CAPTCHA.value == "captcha"


# ==================== ElementType Tests ====================

class TestElementType:
    """Tests for ElementType enum."""
    
    def test_element_type_values(self):
        """Test element type enum values."""
        assert ElementType.BUTTON.value == "button"
        assert ElementType.LINK.value == "link"
        assert ElementType.INPUT_TEXT.value == "input_text"
        assert ElementType.UNKNOWN.value == "unknown"


# ==================== VisualAnalyzer Tests ====================

class TestVisualAnalyzer:
    """Tests for VisualAnalyzer class."""
    
    @pytest.fixture
    def mock_vision_client(self):
        """Create mock vision client."""
        client = MagicMock()
        client.chat_with_image = AsyncMock()
        return client
    
    @pytest.fixture
    def analyzer(self, mock_vision_client):
        """Create analyzer with mock client."""
        return VisualAnalyzer(mock_vision_client, cache_enabled=False)
    
    @pytest.mark.asyncio
    async def test_analyze_page_state_ready(self, analyzer, mock_vision_client):
        """Test page state analysis - ready state."""
        mock_vision_client.chat_with_image.return_value = MagicMock(
            content='{"state": "ready", "confidence": 0.95}'
        )
        
        result = await analyzer._analyze_page_state(b"fake_screenshot")
        
        assert result["state"] == PageState.READY
        assert result["confidence"] == 0.95
    
    @pytest.mark.asyncio
    async def test_analyze_page_state_loading(self, analyzer, mock_vision_client):
        """Test page state analysis - loading state."""
        mock_vision_client.chat_with_image.return_value = MagicMock(
            content='{"state": "loading", "loading_percentage": 75, "confidence": 0.9}'
        )
        
        result = await analyzer._analyze_page_state(b"fake_screenshot")
        
        assert result["state"] == PageState.LOADING
        assert result["loading_percentage"] == 75
    
    @pytest.mark.asyncio
    async def test_analyze_page_state_error(self, analyzer, mock_vision_client):
        """Test page state analysis - error state."""
        mock_vision_client.chat_with_image.return_value = MagicMock(
            content='{"state": "error", "error_message": "404 Not Found", "confidence": 0.95}'
        )
        
        result = await analyzer._analyze_page_state(b"fake_screenshot")
        
        assert result["state"] == PageState.ERROR
        assert result["error_message"] == "404 Not Found"
    
    @pytest.mark.asyncio
    async def test_detect_elements(self, analyzer, mock_vision_client):
        """Test element detection."""
        mock_vision_client.chat_with_image.return_value = MagicMock(
            content='''{
                "elements": [
                    {
                        "bbox": {"x": 100, "y": 200, "width": 80, "height": 40},
                        "type": "button",
                        "description": "Search button",
                        "text_content": "Search",
                        "is_clickable": true,
                        "confidence": 0.95
                    }
                ]
            }'''
        )
        
        elements = await analyzer._detect_elements(b"fake_screenshot")
        
        assert len(elements) == 1
        assert elements[0].element_type == ElementType.BUTTON
        assert elements[0].description == "Search button"
        assert elements[0].is_clickable is True
    
    @pytest.mark.asyncio
    async def test_find_element(self, analyzer, mock_vision_client):
        """Test finding specific element."""
        mock_vision_client.chat_with_image.return_value = MagicMock(
            content='''{
                "found": true,
                "bbox": {"x": 100, "y": 200, "width": 80, "height": 40},
                "type": "input_text",
                "description": "Search input",
                "is_typeable": true,
                "confidence": 0.9
            }'''
        )
        
        element = await analyzer.find_element(
            b"fake_screenshot",
            "search input field"
        )
        
        assert element is not None
        assert element.element_type == ElementType.INPUT_TEXT
        assert element.is_typeable is True
    
    @pytest.mark.asyncio
    async def test_find_element_not_found(self, analyzer, mock_vision_client):
        """Test finding element that doesn't exist."""
        mock_vision_client.chat_with_image.return_value = MagicMock(
            content='{"found": false}'
        )
        
        element = await analyzer.find_element(
            b"fake_screenshot",
            "nonexistent element"
        )
        
        assert element is None
    
    def test_generate_recommendations_ready(self, analyzer):
        """Test recommendation generation for ready state."""
        elements = [
            ElementInfo(
                bounding_box=BoundingBox(0, 0, 100, 50),
                element_type=ElementType.INPUT_TEXT,
                description="Search",
                is_typeable=True
            ),
            ElementInfo(
                bounding_box=BoundingBox(0, 0, 80, 40),
                element_type=ElementType.BUTTON,
                description="Submit",
                is_clickable=True
            )
        ]
        
        recommendations = analyzer._generate_recommendations(
            {"state": PageState.READY},
            elements,
            "Search for Python"
        )
        
        assert any("Search for Python" in r for r in recommendations)
        assert any("input fields" in r for r in recommendations)
        assert any("clickable" in r for r in recommendations)
    
    def test_generate_recommendations_modal(self, analyzer):
        """Test recommendation generation for modal state."""
        recommendations = analyzer._generate_recommendations(
            {"state": PageState.MODAL, "modal_content": "Cookie consent"},
            []
        )
        
        assert any("modal" in r.lower() for r in recommendations)
    
    def test_cache_stats(self, analyzer):
        """Test cache statistics."""
        stats = analyzer.get_cache_stats()
        
        assert "cache_size" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats


# ==================== VisualDiff Tests ====================

class TestVisualDiff:
    """Tests for VisualDiff class."""
    
    @pytest.fixture
    def visual_diff(self):
        """Create visual diff instance."""
        return VisualDiff(similarity_threshold=0.95)
    
    def test_basic_compare_identical(self, visual_diff):
        """Test comparing identical images (basic hash comparison)."""
        # Create simple test images (same content)
        img = b"identical_image_content"
        
        result = visual_diff._basic_compare(img, img)
        
        assert result.are_similar is True
        assert result.similarity_score == 1.0
    
    def test_basic_compare_different(self, visual_diff):
        """Test comparing different images (basic hash comparison)."""
        img1 = b"image_content_1"
        img2 = b"image_content_2"
        
        result = visual_diff._basic_compare(img1, img2)
        
        assert result.are_similar is False
        assert result.similarity_score == 0.0
    
    def test_quick_compare(self, visual_diff):
        """Test quick comparison using basic hash comparison."""
        img = b"same_image"
        
        # Use _basic_compare which doesn't require PIL
        result = visual_diff._basic_compare(img, img)
        
        assert result.are_similar is True
    
    def test_get_similarity_score(self, visual_diff):
        """Test getting similarity score using basic hash comparison."""
        img = b"same_image"
        
        # Use _basic_compare which doesn't require PIL
        result = visual_diff._basic_compare(img, img)
        
        assert result.similarity_score == 1.0


# ==================== VisionCache Tests ====================

class TestVisionCache:
    """Tests for VisionCache class."""
    
    @pytest.fixture
    def cache(self):
        """Create cache instance."""
        return VisionCache(max_size=5, ttl_seconds=60.0)
    
    def test_cache_set_and_get(self, cache):
        """Test setting and getting cache values."""
        screenshot = b"test_screenshot"
        data = {"elements": [{"type": "button"}]}
        
        cache.set(screenshot, "detect_elements", data)
        result = cache.get(screenshot, "detect_elements")
        
        assert result == data
    
    def test_cache_miss(self, cache):
        """Test cache miss."""
        result = cache.get(b"nonexistent", "detect_elements")
        
        assert result is None
    
    def test_cache_stats(self, cache):
        """Test cache statistics."""
        cache.set(b"screenshot", "test", {"data": "value"})
        cache.get(b"screenshot", "test")  # Hit
        cache.get(b"other", "test")  # Miss
        
        stats = cache.get_stats()
        
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate"] == 0.5
    
    def test_cache_invalidation(self, cache):
        """Test cache invalidation."""
        screenshot = b"test_screenshot"
        cache.set(screenshot, "operation1", {"data": 1})
        cache.set(screenshot, "operation2", {"data": 2})
        
        count = cache.invalidate(screenshot)
        
        assert count == 2
        assert cache.get(screenshot, "operation1") is None
    
    def test_cache_clear(self, cache):
        """Test clearing cache."""
        cache.set(b"img1", "op1", {"data": 1})
        cache.set(b"img2", "op2", {"data": 2})
        
        cache.clear()
        
        assert len(cache._cache) == 0
    
    def test_cache_disabled(self):
        """Test cache when disabled."""
        cache = VisionCache(enabled=False)
        
        cache.set(b"img", "op", {"data": 1})
        result = cache.get(b"img", "op")
        
        assert result is None
    
    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = VisionCache(max_size=2)
        
        cache.set(b"img1", "op", {"data": 1})
        cache.set(b"img2", "op", {"data": 2})
        cache.set(b"img3", "op", {"data": 3})  # Should evict img1
        
        assert cache.get(b"img1", "op") is None
        assert cache.get(b"img2", "op") is not None
        assert cache.get(b"img3", "op") is not None
    
    def test_cache_get_or_compute(self, cache):
        """Test get or compute functionality."""
        screenshot = b"test_screenshot"
        compute_count = 0
        
        def compute():
            nonlocal compute_count
            compute_count += 1
            return {"computed": True}
        
        # First call should compute
        result1 = cache.get_or_compute(screenshot, "test", compute)
        assert result1 == {"computed": True}
        assert compute_count == 1
        
        # Second call should use cache
        result2 = cache.get_or_compute(screenshot, "test", compute)
        assert result2 == {"computed": True}
        assert compute_count == 1  # Not incremented
    
    @pytest.mark.asyncio
    async def test_async_get_or_compute(self, cache):
        """Test async get or compute."""
        screenshot = b"test_screenshot"
        compute_count = 0
        
        async def compute():
            nonlocal compute_count
            compute_count += 1
            return {"async_computed": True}
        
        result = await cache.async_get_or_compute(screenshot, "test", compute)
        
        assert result == {"async_computed": True}
        assert compute_count == 1


# ==================== ActionType Tests ====================

class TestVisualActionTypes:
    """Tests for visual action types."""
    
    def test_hover_visual_action_type_exists(self):
        """Test HOVER_VISUAL action type exists."""
        assert ActionType.HOVER_VISUAL.value == "hover_visual"
    
    def test_type_visual_action_type_exists(self):
        """Test TYPE_VISUAL action type exists."""
        assert ActionType.TYPE_VISUAL.value == "type_visual"


# ==================== Integration Tests ====================

class TestVisualAnalyzerIntegration:
    """Integration tests for VisualAnalyzer."""
    
    @pytest.fixture
    def mock_vision_client(self):
        """Create mock vision client."""
        client = MagicMock()
        client.chat_with_image = AsyncMock()
        return client
    
    @pytest.fixture
    def analyzer(self, mock_vision_client):
        """Create analyzer with mock client."""
        return VisualAnalyzer(mock_vision_client, cache_enabled=True)
    
    @pytest.mark.asyncio
    async def test_full_page_analysis(self, analyzer, mock_vision_client):
        """Test complete page analysis workflow."""
        # Mock responses for different calls
        responses = [
            # Page state response
            MagicMock(content='{"state": "ready", "confidence": 0.95}'),
            # Element detection response
            MagicMock(content='''{
                "elements": [
                    {
                        "bbox": {"x": 640, "y": 360, "width": 200, "height": 50},
                        "type": "input_search",
                        "description": "Search bar",
                        "is_typeable": true,
                        "confidence": 0.95
                    }
                ]
            }'''),
            # Summary response
            MagicMock(content='{"summary": "Google search homepage"}'),
        ]
        mock_vision_client.chat_with_image.side_effect = responses
        
        analysis = await analyzer.analyze_page(
            b"fake_screenshot",
            task_context="Search for Python tutorials"
        )
        
        assert analysis.state == PageState.READY
        assert len(analysis.elements) == 1
        assert analysis.elements[0].element_type == ElementType.INPUT_SEARCH
        assert len(analysis.recommended_actions) > 0
    
    @pytest.mark.asyncio
    async def test_analysis_caching(self, analyzer, mock_vision_client):
        """Test that analysis results are cached."""
        mock_vision_client.chat_with_image.return_value = MagicMock(
            content='{"state": "ready", "confidence": 0.9}'
        )
        
        # First analysis
        await analyzer.analyze_page(b"same_screenshot")
        
        # Second analysis with same screenshot should use cache
        await analyzer.analyze_page(b"same_screenshot")
        
        # Vision client should only be called once per analysis step
        # (state + elements + summary = 3 calls for first analysis)
        assert mock_vision_client.chat_with_image.call_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
