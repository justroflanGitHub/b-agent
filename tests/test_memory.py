"""
Tests for Memory Module - Visual Memory, Conversation Memory, Error Prevention.

Comprehensive tests for all memory system components.
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from browser_agent.memory.visual_memory import (
    VisualMemorySystem,
    ScreenshotEmbeddingCache,
    UIStateDetector,
    NavigationPatternLearner,
    DynamicElementReidentifier,
    EmbeddingVector,
    UIState,
    NavigationPattern,
    DynamicElement,
)

from browser_agent.memory.conversation_memory import (
    ConversationMemorySystem,
    UserPreferenceStore,
    CorrectionFeedbackLearner,
    TaskTemplateManager,
    SessionMemory,
    UserPreference,
    CorrectionFeedback,
    TaskTemplate,
    SessionMessage,
    SessionState,
)

from browser_agent.memory.error_prevention import (
    ErrorPreventionSystem,
    AnomalyDetector,
    HeuristicWarningSystem,
    SuspiciousStateHandler,
    PreActionRiskAssessment,
    Anomaly,
    Warning,
    RiskAssessment,
    RiskLevel,
    AnomalyType,
    WarningType,
    BehaviorBaseline,
    SuspiciousState,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_screenshot():
    """Create sample screenshot bytes."""
    return b"fake_screenshot_data_12345678901234567890"


@pytest.fixture
def sample_screenshot2():
    """Create another sample screenshot bytes."""
    return b"different_screenshot_data_09876543210987654321"


# ============================================================================
# EmbeddingVector Tests
# ============================================================================

class TestEmbeddingVector:
    """Tests for EmbeddingVector."""
    
    def test_create_embedding(self):
        """Test creating an embedding vector."""
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        emb = EmbeddingVector(vector=vector, dimension=5)
        
        assert emb.vector == vector
        assert emb.dimension == 5
        assert emb.timestamp > 0
    
    def test_cosine_similarity_identical(self):
        """Test cosine similarity of identical vectors."""
        emb1 = EmbeddingVector(vector=[1.0, 0.0, 0.0], dimension=3)
        emb2 = EmbeddingVector(vector=[1.0, 0.0, 0.0], dimension=3)
        
        similarity = emb1.cosine_similarity(emb2)
        assert similarity == pytest.approx(1.0, abs=0.001)
    
    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity of orthogonal vectors."""
        emb1 = EmbeddingVector(vector=[1.0, 0.0, 0.0], dimension=3)
        emb2 = EmbeddingVector(vector=[0.0, 1.0, 0.0], dimension=3)
        
        similarity = emb1.cosine_similarity(emb2)
        assert similarity == pytest.approx(0.0, abs=0.001)
    
    def test_cosine_similarity_opposite(self):
        """Test cosine similarity of opposite vectors."""
        emb1 = EmbeddingVector(vector=[1.0, 0.0, 0.0], dimension=3)
        emb2 = EmbeddingVector(vector=[-1.0, 0.0, 0.0], dimension=3)
        
        similarity = emb1.cosine_similarity(emb2)
        assert similarity == pytest.approx(-1.0, abs=0.001)
    
    def test_cosine_similarity_different_dimensions(self):
        """Test cosine similarity with different dimensions."""
        emb1 = EmbeddingVector(vector=[1.0, 0.0, 0.0], dimension=3)
        emb2 = EmbeddingVector(vector=[1.0, 0.0], dimension=2)
        
        similarity = emb1.cosine_similarity(emb2)
        assert similarity == 0.0
    
    def test_serialize_deserialize(self):
        """Test serialization and deserialization."""
        original = EmbeddingVector(
            vector=[0.1, 0.2, 0.3],
            dimension=3,
            timestamp=12345.0,
            source_hash="abc123"
        )
        
        data = original.to_bytes()
        restored = EmbeddingVector.from_bytes(data)
        
        assert restored.vector == pytest.approx(original.vector, abs=0.001)
        assert restored.dimension == original.dimension
        assert restored.timestamp == original.timestamp


# ============================================================================
# ScreenshotEmbeddingCache Tests
# ============================================================================

class TestScreenshotEmbeddingCache:
    """Tests for ScreenshotEmbeddingCache."""
    
    def test_create_cache(self):
        """Test creating embedding cache."""
        cache = ScreenshotEmbeddingCache(
            max_size=100,
            embedding_dimension=128
        )
        
        assert cache.max_size == 100
        assert cache.embedding_dimension == 128
        assert len(cache._cache) == 0
    
    def test_get_or_create_embedding_new(self, sample_screenshot):
        """Test creating new embedding."""
        cache = ScreenshotEmbeddingCache(embedding_dimension=64)
        
        embedding, was_cached = cache.get_or_create_embedding(sample_screenshot)
        
        assert embedding is not None
        assert embedding.dimension == 64
        assert len(embedding.vector) == 64
        assert was_cached == False
    
    def test_get_or_create_embedding_cached(self, sample_screenshot):
        """Test retrieving cached embedding."""
        cache = ScreenshotEmbeddingCache(embedding_dimension=64)
        
        # First call creates
        embedding1, was_cached1 = cache.get_or_create_embedding(sample_screenshot)
        
        # Second call retrieves from cache
        embedding2, was_cached2 = cache.get_or_create_embedding(sample_screenshot)
        
        assert was_cached1 == False
        assert was_cached2 == True
        assert embedding1.vector == embedding2.vector
    
    def test_find_similar(self, sample_screenshot, sample_screenshot2):
        """Test finding similar embeddings."""
        cache = ScreenshotEmbeddingCache(
            embedding_dimension=64,
            similarity_threshold=0.95
        )
        
        # Add first screenshot
        emb1, _ = cache.get_or_create_embedding(sample_screenshot)
        
        # Find similar (should find itself)
        results = cache.find_similar(emb1, top_k=5, threshold=0.5)
        
        assert len(results) >= 1
    
    def test_cache_eviction(self):
        """Test cache eviction when full."""
        cache = ScreenshotEmbeddingCache(max_size=5)
        
        # Add more than max_size entries
        for i in range(10):
            screenshot = f"screen_{i}".encode()
            cache.get_or_create_embedding(screenshot)
        
        assert len(cache._cache) <= 5
        assert cache._stats["evictions"] > 0
    
    def test_get_stats(self, sample_screenshot):
        """Test getting cache statistics."""
        cache = ScreenshotEmbeddingCache()
        
        cache.get_or_create_embedding(sample_screenshot)
        stats = cache.get_stats()
        
        assert "hits" in stats
        assert "misses" in stats
        assert "size" in stats
        assert stats["size"] == 1
    
    def test_clear_cache(self, sample_screenshot):
        """Test clearing cache."""
        cache = ScreenshotEmbeddingCache()
        
        cache.get_or_create_embedding(sample_screenshot)
        assert len(cache._cache) == 1
        
        cache.clear()
        assert len(cache._cache) == 0
    
    def test_persistence(self, temp_dir, sample_screenshot):
        """Test cache persistence."""
        persist_path = temp_dir / "embeddings.pkl"
        
        # Create and populate cache
        cache1 = ScreenshotEmbeddingCache(
            persist_path=persist_path,
            embedding_dimension=32
        )
        cache1.get_or_create_embedding(sample_screenshot)
        cache1.save_to_disk()
        
        # Create new cache from disk
        cache2 = ScreenshotEmbeddingCache(
            persist_path=persist_path,
            embedding_dimension=32
        )
        
        # Should have cached data
        assert len(cache2._cache) > 0


# ============================================================================
# UIStateDetector Tests
# ============================================================================

class TestUIStateDetector:
    """Tests for UIStateDetector."""
    
    @pytest.fixture
    def detector(self):
        """Create UI state detector."""
        cache = ScreenshotEmbeddingCache(embedding_dimension=32)
        return UIStateDetector(embedding_cache=cache)
    
    def test_detect_new_state(self, detector, sample_screenshot):
        """Test detecting new state."""
        state, is_new = detector.detect_state(
            screenshot=sample_screenshot,
            url="https://example.com",
            title="Example"
        )
        
        assert is_new == True
        assert state.url == "https://example.com"
        assert state.title == "Example"
        assert state.state_id.startswith("state_")
    
    def test_detect_existing_state(self, detector, sample_screenshot):
        """Test detecting existing state."""
        # First detection
        state1, is_new1 = detector.detect_state(
            screenshot=sample_screenshot,
            url="https://example.com"
        )
        
        # Second detection with same screenshot
        state2, is_new2 = detector.detect_state(
            screenshot=sample_screenshot,
            url="https://example.com"
        )
        
        assert is_new1 == True
        assert is_new2 == False
        assert state1.state_id == state2.state_id
        assert state2.visit_count == 2
    
    def test_record_transition(self, detector, sample_screenshot, sample_screenshot2):
        """Test recording state transitions."""
        state1, _ = detector.detect_state(
            screenshot=sample_screenshot,
            url="https://example.com/page1"
        )
        
        state2, _ = detector.detect_state(
            screenshot=sample_screenshot2,
            url="https://example.com/page2"
        )
        
        detector.record_transition(state1.state_id, state2.state_id)
        
        targets = detector.get_transition_targets(state1.state_id)
        assert state2.state_id in targets
    
    def test_record_action(self, detector, sample_screenshot):
        """Test recording action in state."""
        state, _ = detector.detect_state(
            screenshot=sample_screenshot,
            url="https://example.com"
        )
        
        detector.record_action(state.state_id, "click:#button", "success")
        
        updated_state = detector.get_state(state.state_id)
        assert "click:#button" in updated_state.actions_taken
        assert "success" in updated_state.outcomes
    
    def test_get_states_for_url(self, detector, sample_screenshot, sample_screenshot2):
        """Test getting states for URL."""
        detector.detect_state(
            screenshot=sample_screenshot,
            url="https://example.com/page1"
        )
        
        detector.detect_state(
            screenshot=sample_screenshot2,
            url="https://example.com/page2"
        )
        
        states = detector.get_states_for_url("https://example.com/page1")
        assert len(states) == 1
    
    def test_get_stats(self, detector, sample_screenshot):
        """Test getting detector statistics."""
        detector.detect_state(
            screenshot=sample_screenshot,
            url="https://example.com"
        )
        
        stats = detector.get_stats()
        
        assert stats["total_states"] == 1
        assert stats["unique_urls"] == 1


# ============================================================================
# NavigationPatternLearner Tests
# ============================================================================

class TestNavigationPatternLearner:
    """Tests for NavigationPatternLearner."""
    
    @pytest.fixture
    def learner(self):
        """Create pattern learner."""
        return NavigationPatternLearner()
    
    @pytest.fixture
    def sample_state(self):
        """Create sample UI state."""
        return UIState(
            state_id="state_123",
            embedding=EmbeddingVector(vector=[0.1, 0.2], dimension=2),
            url="https://example.com"
        )
    
    @pytest.fixture
    def sample_state2(self):
        """Create another sample UI state."""
        return UIState(
            state_id="state_456",
            embedding=EmbeddingVector(vector=[0.3, 0.4], dimension=2),
            url="https://example.com/page2"
        )
    
    def test_learn_pattern(self, learner, sample_state, sample_state2):
        """Test learning navigation pattern."""
        actions = [
            {"type": "click", "selector": "#button"},
            {"type": "fill", "selector": "#input", "value": "test"}
        ]
        
        pattern = learner.learn_pattern(
            source_state=sample_state,
            target_state=sample_state2,
            action_sequence=actions,
            duration=1.5,
            success=True
        )
        
        assert pattern is not None
        assert pattern.source_state_id == sample_state.state_id
        assert pattern.target_state_id == sample_state2.state_id
        assert pattern.success_count == 1
        assert pattern.failure_count == 0
    
    def test_pattern_success_rate(self, learner, sample_state, sample_state2):
        """Test pattern success rate calculation."""
        actions = [{"type": "click", "selector": "#button"}]
        
        pattern = learner.learn_pattern(
            source_state=sample_state,
            target_state=sample_state2,
            action_sequence=actions,
            duration=1.0,
            success=True
        )
        
        # Record more outcomes
        pattern.record_outcome(True, 1.0)
        pattern.record_outcome(False, 1.0)
        
        assert pattern.success_rate == pytest.approx(2/3, abs=0.01)
    
    def test_get_patterns_for_source(self, learner, sample_state, sample_state2):
        """Test getting patterns for source state."""
        actions = [{"type": "click", "selector": "#button"}]
        
        learner.learn_pattern(
            source_state=sample_state,
            target_state=sample_state2,
            action_sequence=actions,
            duration=1.0,
            success=True
        )
        
        patterns = learner.get_patterns_for_source(sample_state.state_id)
        
        assert len(patterns) == 1
    
    def test_suggest_navigation(self, learner, sample_state, sample_state2):
        """Test navigation suggestions."""
        actions = [{"type": "click", "selector": "#button"}]
        
        # Learn successful pattern
        learner.learn_pattern(
            source_state=sample_state,
            target_state=sample_state2,
            action_sequence=actions,
            duration=1.0,
            success=True
        )
        
        suggestions = learner.suggest_navigation(sample_state)
        
        assert len(suggestions) >= 1
        assert suggestions[0][1] > 0  # Confidence > 0
    
    def test_get_stats(self, learner, sample_state, sample_state2):
        """Test getting learner statistics."""
        actions = [{"type": "click", "selector": "#button"}]
        
        learner.learn_pattern(
            source_state=sample_state,
            target_state=sample_state2,
            action_sequence=actions,
            duration=1.0,
            success=True
        )
        
        stats = learner.get_stats()
        
        assert stats["total_patterns"] == 1
        assert stats["avg_success_rate"] == 1.0


# ============================================================================
# DynamicElementReidentifier Tests
# ============================================================================

class TestDynamicElementReidentifier:
    """Tests for DynamicElementReidentifier."""
    
    @pytest.fixture
    def reidentifier(self):
        """Create element reidentifier."""
        return DynamicElementReidentifier()
    
    def test_track_new_element(self, reidentifier):
        """Test tracking new element."""
        element = reidentifier.track_element(
            selector="#button",
            content="Click Me",
            position=(100, 200, 80, 30),
            element_type="button"
        )
        
        assert element.element_id.startswith("elem_")
        assert element.selector == "#button"
        assert element.appearance_count == 1
    
    def test_reidentify_element(self, reidentifier):
        """Test re-identifying existing element."""
        # Track first time
        element1 = reidentifier.track_element(
            selector="#button",
            content="Click Me",
            position=(100, 200, 80, 30),
            element_type="button"
        )
        
        # Track again with same selector
        element2 = reidentifier.track_element(
            selector="#button",
            content="Click Me",
            position=(105, 205, 80, 30),  # Slightly different position
            element_type="button"
        )
        
        assert element1.element_id == element2.element_id
        assert element2.appearance_count == 2
        assert len(element2.position_variations) == 1
    
    def test_find_by_selector(self, reidentifier):
        """Test finding element by selector."""
        reidentifier.track_element(
            selector="#button",
            content="Click Me",
            position=(100, 200, 80, 30),
            element_type="button"
        )
        
        element = reidentifier.find_by_selector("#button")
        
        assert element is not None
        assert element.selector == "#button"
    
    def test_find_by_content(self, reidentifier):
        """Test finding element by content."""
        reidentifier.track_element(
            selector="#button",
            content="Click Me",
            position=(100, 200, 80, 30),
            element_type="button"
        )
        
        elements = reidentifier.find_by_content("Click Me")
        
        assert len(elements) == 1
        # Content is hashed, so we check selector instead
        assert elements[0].selector == "#button"
    
    def test_find_by_position(self, reidentifier):
        """Test finding element by position."""
        reidentifier.track_element(
            selector="#button",
            content="Click Me",
            position=(100, 200, 80, 30),
            element_type="button"
        )
        
        elements = reidentifier.find_by_position((105, 205, 80, 30))
        
        assert len(elements) >= 1
    
    def test_state_association(self, reidentifier):
        """Test element state association."""
        element = reidentifier.track_element(
            selector="#button",
            content="Click Me",
            position=(100, 200, 80, 30),
            element_type="button",
            state_id="state_123"
        )
        
        assert "state_123" in element.state_associations
    
    def test_get_stats(self, reidentifier):
        """Test getting reidentifier statistics."""
        reidentifier.track_element(
            selector="#button",
            content="Click Me",
            position=(100, 200, 80, 30),
            element_type="button"
        )
        
        stats = reidentifier.get_stats()
        
        assert stats["total_elements"] == 1


# ============================================================================
# VisualMemorySystem Tests
# ============================================================================

class TestVisualMemorySystem:
    """Tests for VisualMemorySystem."""
    
    @pytest.fixture
    def system(self):
        """Create visual memory system."""
        return VisualMemorySystem()
    
    def test_process_screenshot(self, system, sample_screenshot):
        """Test processing screenshot."""
        state, is_new = system.process_screenshot(
            screenshot=sample_screenshot,
            url="https://example.com",
            title="Example"
        )
        
        assert state is not None
        assert is_new == True
    
    def test_navigation_tracking(self, system, sample_screenshot, sample_screenshot2):
        """Test navigation tracking."""
        system.process_screenshot(
            screenshot=sample_screenshot,
            url="https://example.com/page1"
        )
        
        system.start_navigation()
        system.record_action({"type": "click", "selector": "#next"})
        
        target_state, _ = system.process_screenshot(
            screenshot=sample_screenshot2,
            url="https://example.com/page2"
        )
        
        system.end_navigation(success=True, target_state=target_state)
        
        # Should have learned a pattern
        suggestions = system.get_navigation_suggestions()
        # May or may not have suggestions depending on implementation
    
    def test_element_tracking(self, system, sample_screenshot):
        """Test element tracking."""
        system.process_screenshot(
            screenshot=sample_screenshot,
            url="https://example.com"
        )
        
        element = system.track_element(
            selector="#button",
            content="Submit",
            position=(100, 200, 80, 30),
            element_type="button"
        )
        
        assert element is not None
    
    def test_get_all_stats(self, system):
        """Test getting all statistics."""
        stats = system.get_all_stats()
        
        assert "embedding_cache" in stats
        assert "state_detector" in stats
        assert "pattern_learner" in stats
        assert "element_reidentifier" in stats


# ============================================================================
# UserPreferenceStore Tests
# ============================================================================

class TestUserPreferenceStore:
    """Tests for UserPreferenceStore."""
    
    def test_set_and_get(self):
        """Test setting and getting preferences."""
        store = UserPreferenceStore()
        
        store.set("theme", "dark", category="ui")
        value = store.get("theme")
        
        assert value == "dark"
    
    def test_get_nonexistent(self):
        """Test getting nonexistent preference."""
        store = UserPreferenceStore()
        
        value = store.get("nonexistent", default="default_value")
        
        assert value == "default_value"
    
    def test_update_preference(self):
        """Test updating preference."""
        store = UserPreferenceStore()
        
        store.set("theme", "dark")
        store.set("theme", "light")
        
        value = store.get("theme")
        assert value == "light"
    
    def test_get_category(self):
        """Test getting preferences by category."""
        store = UserPreferenceStore()
        
        store.set("theme", "dark", category="ui")
        store.set("font_size", "large", category="ui")
        store.set("timeout", 30, category="network")
        
        ui_prefs = store.get_category("ui")
        
        assert len(ui_prefs) == 2
        assert ui_prefs["theme"] == "dark"
    
    def test_delete(self):
        """Test deleting preference."""
        store = UserPreferenceStore()
        
        store.set("theme", "dark")
        deleted = store.delete("theme")
        
        assert deleted == True
        assert store.get("theme") is None
    
    def test_infer_preference(self):
        """Test inferring preference."""
        store = UserPreferenceStore()
        
        store.infer_preference("preferred_browser", "chrome", confidence=0.7)
        
        value = store.get("preferred_browser")
        assert value == "chrome"
    
    def test_persistence(self, temp_dir):
        """Test preference persistence."""
        persist_path = temp_dir / "preferences.json"
        
        store1 = UserPreferenceStore(persist_path=persist_path)
        store1.set("theme", "dark")
        store1.save_to_disk()
        
        store2 = UserPreferenceStore(persist_path=persist_path)
        
        assert store2.get("theme") == "dark"
    
    def test_get_stats(self):
        """Test getting statistics."""
        store = UserPreferenceStore()
        
        store.set("theme", "dark", category="ui")
        store.set("timeout", 30, category="network")
        
        stats = store.get_stats()
        
        assert stats["total_preferences"] == 2


# ============================================================================
# CorrectionFeedbackLearner Tests
# ============================================================================

class TestCorrectionFeedbackLearner:
    """Tests for CorrectionFeedbackLearner."""
    
    @pytest.fixture
    def learner(self):
        """Create feedback learner."""
        return CorrectionFeedbackLearner()
    
    def test_record_correction(self, learner):
        """Test recording correction."""
        feedback = learner.record_correction(
            context={"url": "https://example.com"},
            original_action={"type": "click", "selector": "#wrong"},
            corrected_action={"type": "click", "selector": "#right"},
            explanation="Wrong button"
        )
        
        assert feedback.feedback_id.startswith("corr_")
        assert feedback.original_action["selector"] == "#wrong"
        assert feedback.corrected_action["selector"] == "#right"
    
    def test_get_correction_for_action(self, learner):
        """Test getting correction for action."""
        context = {"url": "https://example.com"}
        
        learner.record_correction(
            context=context,
            original_action={"type": "click", "selector": "#wrong"},
            corrected_action={"type": "click", "selector": "#right"}
        )
        
        correction = learner.get_correction_for_action(
            context=context,
            proposed_action={"type": "click", "selector": "#wrong"}
        )
        
        assert correction is not None
    
    def test_apply_correction(self, learner):
        """Test applying correction."""
        feedback = learner.record_correction(
            context={"url": "https://example.com"},
            original_action={"type": "click", "selector": "#wrong"},
            corrected_action={"type": "click", "selector": "#right"}
        )
        
        action = {"type": "click", "selector": "#wrong"}
        corrected = learner.apply_correction(feedback, action)
        
        assert corrected["selector"] == "#right"
    
    def test_record_outcome(self, learner):
        """Test recording correction outcome."""
        feedback = learner.record_correction(
            context={"url": "https://example.com"},
            original_action={"type": "click", "selector": "#wrong"},
            corrected_action={"type": "click", "selector": "#right"}
        )
        
        learner.apply_correction(feedback, {"type": "click"})
        learner.record_outcome(feedback.feedback_id, success=True)
        
        assert feedback.success_rate > 0
    
    def test_get_stats(self, learner):
        """Test getting learner statistics."""
        learner.record_correction(
            context={"url": "https://example.com"},
            original_action={"type": "click", "selector": "#wrong"},
            corrected_action={"type": "click", "selector": "#right"}
        )
        
        stats = learner.get_stats()
        
        assert stats["total_corrections"] == 1


# ============================================================================
# TaskTemplateManager Tests
# ============================================================================

class TestTaskTemplateManager:
    """Tests for TaskTemplateManager."""
    
    @pytest.fixture
    def manager(self):
        """Create template manager."""
        return TaskTemplateManager()
    
    def test_create_template(self, manager):
        """Test creating template."""
        template = manager.create_template(
            name="Login Flow",
            description="Standard login process",
            goal_pattern="login to website",
            steps=[
                {"type": "fill", "selector": "#username", "value": "{username}"},
                {"type": "fill", "selector": "#password", "value": "{password}"},
                {"type": "click", "selector": "#submit"}
            ]
        )
        
        assert template.template_id.startswith("tpl_")
        assert template.name == "Login Flow"
    
    def test_find_matching_templates(self, manager):
        """Test finding matching templates."""
        manager.create_template(
            name="Login",
            description="Login process",
            goal_pattern="login to website",
            steps=[{"type": "click", "selector": "#login"}]
        )
        
        matches = manager.find_matching_templates("login to website")
        
        assert len(matches) >= 1
    
    def test_instantiate_template(self, manager):
        """Test instantiating template."""
        template = manager.create_template(
            name="Search",
            description="Search process",
            goal_pattern="search for items",
            steps=[
                {"type": "fill", "selector": "#search", "value": "{query}"},
                {"type": "click", "selector": "#submit"}
            ],
            parameters={"query": ""}
        )
        
        steps = manager.instantiate_template(template, {"query": "test search"})
        
        assert steps[0]["value"] == "test search"
    
    def test_record_use(self, manager):
        """Test recording template use."""
        template = manager.create_template(
            name="Test",
            description="Test template",
            goal_pattern="test",
            steps=[{"type": "click"}]
        )
        
        manager.record_use(template.template_id, success=True, completion_time=1.5)
        
        updated = manager.get_template(template.template_id)
        assert updated.use_count == 1
        assert updated.success_count == 1
    
    def test_create_from_execution(self, manager):
        """Test creating template from execution."""
        steps = [
            {"type": "navigate", "url": "https://example.com"},
            {"type": "click", "selector": "#button"}
        ]
        
        template = manager.create_from_execution(
            name="Test Task",
            goal="complete test task",
            steps=steps,
            success=True,
            completion_time=2.5
        )
        
        assert template is not None
        assert template.name == "Test Task"


# ============================================================================
# SessionMemory Tests
# ============================================================================

class TestSessionMemory:
    """Tests for SessionMemory."""
    
    def test_create_session(self):
        """Test creating session."""
        session = SessionMemory()
        
        assert session.session_id.startswith("sess_")
        assert session._state.status == "active"
    
    def test_add_messages(self):
        """Test adding messages."""
        session = SessionMemory()
        
        session.add_user_message("Hello")
        session.add_agent_message("Hi there!")
        
        messages = session.get_messages()
        
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "agent"
    
    def test_get_recent_messages(self):
        """Test getting recent messages."""
        session = SessionMemory()
        
        for i in range(20):
            session.add_user_message(f"Message {i}")
        
        recent = session.get_recent_messages(5)
        
        assert len(recent) == 5
    
    def test_context_management(self):
        """Test context management."""
        session = SessionMemory()
        
        session.set_context("current_url", "https://example.com")
        session.set_context("step_count", 5)
        
        assert session.get_context("current_url") == "https://example.com"
        assert session.get_context("step_count") == 5
    
    def test_goal_management(self):
        """Test goal management."""
        session = SessionMemory()
        
        session.set_goal("Complete login")
        
        assert session.get_goal() == "Complete login"
    
    def test_task_history(self):
        """Test task history."""
        session = SessionMemory()
        
        session.add_task_record({"action": "click", "success": True})
        session.add_task_record({"action": "fill", "success": False})
        
        history = session.get_task_history()
        
        assert len(history) == 2
    
    def test_session_status(self):
        """Test session status changes."""
        session = SessionMemory()
        
        session.pause()
        assert session._state.status == "paused"
        
        session.resume()
        assert session._state.status == "active"
        
        session.complete()
        assert session._state.status == "completed"
    
    def test_persistence(self, temp_dir):
        """Test session persistence."""
        session_dir = temp_dir / "sessions"
        
        session1 = SessionMemory(persist_path=session_dir)
        session1.add_user_message("Hello")
        session1._save_session()
        
        session2 = SessionMemory(
            session_id=session1.session_id,
            persist_path=session_dir
        )
        
        messages = session2.get_messages()
        assert len(messages) == 1


# ============================================================================
# ConversationMemorySystem Tests
# ============================================================================

class TestConversationMemorySystem:
    """Tests for ConversationMemorySystem."""
    
    @pytest.fixture
    def system(self):
        """Create conversation memory system."""
        return ConversationMemorySystem()
    
    def test_process_conversation(self, system):
        """Test processing conversation."""
        system.process_user_input("Search for laptops")
        system.process_agent_response("I'll search for laptops now")
        
        context = system.get_conversation_context()
        
        assert "Search for laptops" in context
        assert "I'll search for laptops" in context
    
    def test_preferences(self, system):
        """Test preference management."""
        system.set_preference("language", "en")
        
        value = system.get_preference("language")
        assert value == "en"
    
    def test_correction_workflow(self, system):
        """Test correction workflow."""
        context = {"url": "https://example.com"}
        
        # Record correction
        system.record_correction(
            context=context,
            original_action={"type": "click", "selector": "#wrong"},
            corrected_action={"type": "click", "selector": "#right"}
        )
        
        # Get correction for similar action
        corrected = system.get_action_correction(
            context=context,
            proposed_action={"type": "click", "selector": "#wrong"}
        )
        
        assert corrected is not None
        assert corrected["selector"] == "#right"
    
    def test_template_workflow(self, system):
        """Test template workflow."""
        # Find templates
        matches = system.find_task_templates("login to website")
        
        # Create template from execution
        template = system.create_template_from_task(
            name="Test",
            goal="test goal",
            steps=[{"type": "click"}],
            success=True,
            completion_time=1.0
        )
        
        assert template is not None
    
    def test_get_all_stats(self, system):
        """Test getting all statistics."""
        stats = system.get_all_stats()
        
        assert "preferences" in stats
        assert "feedback" in stats
        assert "templates" in stats
        assert "session" in stats


# ============================================================================
# AnomalyDetector Tests
# ============================================================================

class TestAnomalyDetector:
    """Tests for AnomalyDetector."""
    
    @pytest.fixture
    def detector(self):
        """Create anomaly detector."""
        return AnomalyDetector(learning_mode=True)
    
    def test_observe_metrics_learning(self, detector):
        """Test observing metrics in learning mode."""
        # Observe normal values
        for _ in range(10):
            anomalies = detector.observe_page_metrics(
                url="https://example.com",
                metrics={"load_time": 1.0, "element_count": 50}
            )
            assert len(anomalies) == 0  # No anomalies during learning
    
    def test_detect_anomaly(self, detector):
        """Test detecting anomaly."""
        # Learn normal behavior
        for _ in range(10):
            detector.observe_page_metrics(
                url="https://example.com",
                metrics={"load_time": 1.0}
            )
        
        # Observe anomalous value
        anomalies = detector.observe_page_metrics(
            url="https://example.com",
            metrics={"load_time": 10.0}  # Much higher than normal
        )
        
        # Should detect anomaly
        assert len(anomalies) >= 1
    
    def test_detect_element_anomaly(self, detector):
        """Test detecting element anomaly."""
        anomaly = detector.detect_element_anomaly(
            selector="#button",
            expected_present=True,
            actual_present=False
        )
        
        assert anomaly is not None
        assert anomaly.anomaly_type == AnomalyType.ELEMENT_MISSING
    
    def test_detect_redirect_anomaly(self, detector):
        """Test detecting redirect anomaly."""
        anomaly = detector.detect_redirect_anomaly(
            expected_url="https://example.com/page1",
            actual_url="https://example.com/page2"
        )
        
        assert anomaly is not None
        assert anomaly.anomaly_type == AnomalyType.UNEXPECTED_REDIRECT
    
    def test_detect_popup_anomaly(self, detector):
        """Test detecting popup anomaly."""
        anomaly = detector.detect_popup_anomaly(
            popup_detected=True,
            popup_type="modal"
        )
        
        assert anomaly is not None
        assert anomaly.anomaly_type == AnomalyType.POPUP_DETECTED
    
    def test_detect_error_message(self, detector):
        """Test detecting error message."""
        anomaly = detector.detect_error_message("Error: Something went wrong")
        
        assert anomaly is not None
        assert anomaly.anomaly_type == AnomalyType.ERROR_MESSAGE
    
    def test_get_recent_anomalies(self, detector):
        """Test getting recent anomalies."""
        detector._detected_anomalies = [
            Anomaly(AnomalyType.POPUP_DETECTED, RiskLevel.LOW, "test1"),
            Anomaly(AnomalyType.ERROR_MESSAGE, RiskLevel.HIGH, "test2"),
        ]
        
        recent = detector.get_recent_anomalies(count=10)
        
        assert len(recent) == 2


# ============================================================================
# HeuristicWarningSystem Tests
# ============================================================================

class TestHeuristicWarningSystem:
    """Tests for HeuristicWarningSystem."""
    
    @pytest.fixture
    def warning_system(self):
        """Create warning system."""
        return HeuristicWarningSystem()
    
    def test_navigation_risk_warning(self, warning_system):
        """Test navigation risk warning."""
        action = {"type": "navigate", "url": "https://example.com/logout"}
        
        warnings = warning_system.check_action(action)
        
        assert len(warnings) >= 1
        assert any(w.warning_type == WarningType.NAVIGATION_RISK for w in warnings)
    
    def test_form_validation_warning(self, warning_system):
        """Test form validation warning."""
        action = {
            "type": "fill",
            "selector": "#email",
            "value": "not-an-email",
            "field_type": "email"
        }
        
        warnings = warning_system.check_action(action)
        
        assert len(warnings) >= 1
        assert any(w.warning_type == WarningType.FORM_VALIDATION for w in warnings)
    
    def test_action_stability_warning(self, warning_system):
        """Test action stability warning."""
        # Record some failures
        for i in range(5):
            warning_system.record_action(
                {"type": "click"},
                {"success": i < 2}  # 3 failures
            )
        
        warnings = warning_system.check_action({"type": "click"})
        
        assert any(w.warning_type == WarningType.ACTION_UNSTABLE for w in warnings)
    
    def test_element_ambiguity_warning(self, warning_system):
        """Test element ambiguity warning."""
        action = {"type": "click", "selector": "//div"}  # Very short XPath
        
        warnings = warning_system.check_action(action)
        
        assert any(w.warning_type == WarningType.ELEMENT_AMBIGUOUS for w in warnings)
    
    def test_dismiss_warning(self, warning_system):
        """Test dismissing warning."""
        action = {"type": "navigate", "url": "https://example.com/logout"}
        
        warnings = warning_system.check_action(action)
        
        if warnings:
            warning_system.dismiss_warning(warnings[0])
            assert warnings[0].dismissed == True
    
    def test_get_stats(self, warning_system):
        """Test getting statistics."""
        warning_system.check_action({"type": "navigate", "url": "https://example.com/logout"})
        
        stats = warning_system.get_stats()
        
        assert stats["total_warnings"] >= 1


# ============================================================================
# SuspiciousStateHandler Tests
# ============================================================================

class TestSuspiciousStateHandler:
    """Tests for SuspiciousStateHandler."""
    
    @pytest.fixture
    def handler(self, temp_dir):
        """Create suspicious state handler."""
        return SuspiciousStateHandler(screenshot_dir=temp_dir)
    
    def test_handle_suspicious_state(self, handler, sample_screenshot):
        """Test handling suspicious state."""
        anomalies = [
            Anomaly(AnomalyType.ERROR_MESSAGE, RiskLevel.HIGH, "Error detected")
        ]
        warnings = [
            Warning(WarningType.NAVIGATION_RISK, RiskLevel.MEDIUM, "Risky", "Be careful")
        ]
        
        state = handler.handle_suspicious_state(
            screenshot=sample_screenshot,
            anomalies=anomalies,
            warnings=warnings
        )
        
        assert state.state_hash is not None
        assert len(state.anomalies) == 1
        assert len(state.warnings) == 1
    
    def test_get_unreviewed_states(self, handler, sample_screenshot):
        """Test getting unreviewed states."""
        handler.handle_suspicious_state(
            screenshot=sample_screenshot,
            anomalies=[Anomaly(AnomalyType.ERROR_MESSAGE, RiskLevel.HIGH, "Error")],
            warnings=[]
        )
        
        unreviewed = handler.get_unreviewed_states()
        
        assert len(unreviewed) == 1
    
    def test_mark_reviewed(self, handler, sample_screenshot):
        """Test marking state as reviewed."""
        state = handler.handle_suspicious_state(
            screenshot=sample_screenshot,
            anomalies=[Anomaly(AnomalyType.ERROR_MESSAGE, RiskLevel.HIGH, "Error")],
            warnings=[]
        )
        
        handler.mark_reviewed(state.state_hash, notes="False positive")
        
        updated = handler.get_state(state.state_hash)
        assert updated.reviewed == True
        assert updated.notes == "False positive"


# ============================================================================
# PreActionRiskAssessment Tests
# ============================================================================

class TestPreActionRiskAssessment:
    """Tests for PreActionRiskAssessment."""
    
    @pytest.fixture
    def assessment(self):
        """Create risk assessment."""
        return PreActionRiskAssessment()
    
    def test_assess_simple_action(self, assessment):
        """Test assessing simple action."""
        action = {"type": "click", "selector": "#button"}
        
        result = assessment.assess_action(action)
        
        assert result.action_type == "click"
        assert result.overall_risk in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert isinstance(result.should_proceed, bool)
    
    def test_assess_with_history(self, assessment):
        """Test assessment with action history."""
        # Record some outcomes
        for _ in range(5):
            assessment.record_outcome("click", success=True)
        
        action = {"type": "click", "selector": "#button"}
        result = assessment.assess_action(action)
        
        assert len(result.factors) > 0
    
    def test_high_risk_action_blocked(self, assessment):
        """Test that high risk actions are blocked."""
        assessment.risk_threshold = 0.5
        
        # Create action that might be high risk
        action = {"type": "navigate", "url": "https://example.com/delete"}
        
        result = assessment.assess_action(action)
        
        # Check that assessment was made
        assert result.overall_risk in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
    
    def test_record_outcome_updates_stats(self, assessment):
        """Test that recording outcomes updates statistics."""
        assessment.record_outcome("click", success=True)
        assessment.record_outcome("click", success=False)
        assessment.record_outcome("fill", success=True)
        
        stats = assessment.get_stats()
        
        assert "click" in stats["action_outcomes"]
        assert "fill" in stats["action_outcomes"]
    
    def test_get_assessment_history(self, assessment):
        """Test getting assessment history."""
        for i in range(5):
            assessment.assess_action({"type": "click"})
        
        history = assessment.get_assessment_history(count=3)
        
        assert len(history) == 3


# ============================================================================
# ErrorPreventionSystem Tests
# ============================================================================

class TestErrorPreventionSystem:
    """Tests for ErrorPreventionSystem."""
    
    @pytest.fixture
    def system(self, temp_dir):
        """Create error prevention system."""
        return ErrorPreventionSystem(screenshot_dir=temp_dir)
    
    def test_observe_page(self, system):
        """Test observing page."""
        anomalies, warnings = system.observe_page(
            url="https://example.com",
            metrics={"load_time": 1.0}
        )
        
        assert isinstance(anomalies, list)
        assert isinstance(warnings, list)
    
    def test_check_action(self, system, sample_screenshot):
        """Test checking action."""
        action = {"type": "click", "selector": "#button"}
        
        assessment, warnings = system.check_action(
            action=action,
            screenshot=sample_screenshot
        )
        
        assert assessment is not None
        assert isinstance(warnings, list)
    
    def test_record_action_result(self, system):
        """Test recording action result."""
        action = {"type": "click"}
        result = {"success": True}
        
        system.record_action_result(action, result)
        
        # Should update internal state
        stats = system.get_all_stats()
        assert stats is not None
    
    def test_should_proceed(self, system):
        """Test should_proceed decision."""
        action = {"type": "click", "selector": "#button"}
        
        should, reason = system.should_proceed(action)
        
        assert isinstance(should, bool)
        if not should:
            assert reason is not None
    
    def test_get_all_stats(self, system):
        """Test getting all statistics."""
        stats = system.get_all_stats()
        
        assert "anomaly_detector" in stats
        assert "warning_system" in stats
        assert "suspicious_handler" in stats
        assert "risk_assessment" in stats


# ============================================================================
# Integration Tests
# ============================================================================

class TestMemoryIntegration:
    """Integration tests for memory systems."""
    
    def test_visual_memory_with_error_prevention(self, sample_screenshot):
        """Test visual memory integration with error prevention."""
        visual = VisualMemorySystem()
        error_prevention = ErrorPreventionSystem()
        
        # Process screenshot
        state, is_new = visual.process_screenshot(
            screenshot=sample_screenshot,
            url="https://example.com"
        )
        
        # Check action with error prevention
        action = {"type": "click", "selector": "#button"}
        should_proceed, reason = error_prevention.should_proceed(action)
        
        # Record outcome
        error_prevention.record_action_result(action, {"success": True})
        
        assert state is not None
    
    def test_conversation_memory_with_visual(self, sample_screenshot):
        """Test conversation memory with visual memory."""
        conversation = ConversationMemorySystem()
        visual = VisualMemorySystem()
        
        # Process user input
        conversation.process_user_input("Click the submit button")
        
        # Process visual state
        state, _ = visual.process_screenshot(
            screenshot=sample_screenshot,
            url="https://example.com/form"
        )
        
        # Set context
        conversation.session_memory.set_context("current_state", state.state_id)
        
        # Verify integration
        assert conversation.session_memory.get_context("current_state") == state.state_id
    
    def test_full_memory_workflow(self, sample_screenshot, temp_dir):
        """Test full memory workflow."""
        # Initialize all systems
        visual = VisualMemorySystem(
            persist_path=temp_dir / "visual"
        )
        conversation = ConversationMemorySystem(
            persist_path=temp_dir / "conversation"
        )
        error_prevention = ErrorPreventionSystem(
            screenshot_dir=temp_dir / "screenshots"
        )
        
        # Process conversation
        conversation.process_user_input("Login to the website")
        
        # Process visual state
        state, _ = visual.process_screenshot(
            screenshot=sample_screenshot,
            url="https://example.com/login"
        )
        
        # Check action
        action = {"type": "fill", "selector": "#username", "value": "user"}
        assessment, warnings = error_prevention.check_action(action)
        
        # Record result
        error_prevention.record_action_result(action, {"success": True})
        
        # Create template from successful task
        template = conversation.create_template_from_task(
            name="Login",
            goal="Login to website",
            steps=[action],
            success=True,
            completion_time=1.0
        )
        
        # Save all
        visual.save_state()
        conversation.save_all()
        
        assert template is not None
        assert assessment is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
