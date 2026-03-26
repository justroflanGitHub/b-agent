"""
Visual Memory System - Advanced visual memory for browser agent.

Provides:
- Screenshot embedding cache with perceptual hashing
- Similar UI state detection using embeddings
- Learned navigation patterns
- Fast re-identification of dynamic elements
"""

import hashlib
import logging
import time
import json
import pickle
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple, Callable
from pathlib import Path
import struct
import math

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class EmbeddingVector:
    """Embedding vector for visual content."""
    vector: List[float]
    dimension: int
    timestamp: float = field(default_factory=time.time)
    source_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_bytes(self) -> bytes:
        """Serialize embedding to bytes."""
        return struct.pack(
            f"fi{self.dimension}f",
            self.timestamp,
            self.dimension,
            *self.vector
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "EmbeddingVector":
        """Deserialize embedding from bytes."""
        timestamp, dimension = struct.unpack_from("fi", data)
        vector = list(struct.unpack_from(f"{dimension}f", data, 8))
        return cls(vector=vector, dimension=dimension, timestamp=timestamp)
    
    def cosine_similarity(self, other: "EmbeddingVector") -> float:
        """Calculate cosine similarity with another embedding."""
        if self.dimension != other.dimension:
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(self.vector, other.vector))
        norm_a = math.sqrt(sum(a * a for a in self.vector))
        norm_b = math.sqrt(sum(b * b for b in other.vector))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)


@dataclass
class UIState:
    """Represents a UI state with embedding and metadata."""
    state_id: str
    embedding: EmbeddingVector
    url: str
    title: str = ""
    timestamp: float = field(default_factory=time.time)
    element_count: int = 0
    interactive_count: int = 0
    screenshot_hash: str = ""
    visit_count: int = 1
    last_visit: float = field(default_factory=time.time)
    actions_taken: List[str] = field(default_factory=list)
    outcomes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "state_id": self.state_id,
            "embedding": {
                "vector": self.embedding.vector[:10],  # Truncate for readability
                "dimension": self.embedding.dimension,
            },
            "url": self.url,
            "title": self.title,
            "timestamp": self.timestamp,
            "element_count": self.element_count,
            "interactive_count": self.interactive_count,
            "screenshot_hash": self.screenshot_hash,
            "visit_count": self.visit_count,
            "last_visit": self.last_visit,
            "actions_taken": self.actions_taken,
            "outcomes": self.outcomes,
        }


@dataclass
class NavigationPattern:
    """Learned navigation pattern."""
    pattern_id: str
    source_state_id: str
    target_state_id: str
    action_sequence: List[Dict[str, Any]]
    success_count: int = 0
    failure_count: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    last_used: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    def record_outcome(self, success: bool, duration: float):
        """Record navigation outcome."""
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.total_duration += duration
        self.avg_duration = self.total_duration / (self.success_count + self.failure_count)
        self.last_used = time.time()


@dataclass
class DynamicElement:
    """Tracked dynamic element."""
    element_id: str
    selector: str
    content_hash: str
    position: Tuple[int, int, int, int]  # x, y, width, height
    element_type: str
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    appearance_count: int = 1
    state_associations: List[str] = field(default_factory=list)
    position_variations: List[Tuple[int, int, int, int]] = field(default_factory=list)
    
    def update_position(self, new_position: Tuple[int, int, int, int]):
        """Update element position and track variations."""
        if new_position != self.position:
            self.position_variations.append(self.position)
            self.position = new_position
        self.last_seen = time.time()
        self.appearance_count += 1


# ============================================================================
# Screenshot Embedding Cache
# ============================================================================

class ScreenshotEmbeddingCache:
    """
    Cache for screenshot embeddings with perceptual hashing.
    
    Features:
    - LRU eviction policy
    - Perceptual hash for similarity lookup
    - Persistent storage support
    - Embedding compression
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        embedding_dimension: int = 512,
        similarity_threshold: float = 0.95,
        persist_path: Optional[Path] = None
    ):
        """
        Initialize embedding cache.
        
        Args:
            max_size: Maximum number of embeddings to cache
            embedding_dimension: Dimension of embedding vectors
            similarity_threshold: Threshold for considering embeddings similar
            persist_path: Path for persistent storage
        """
        self.max_size = max_size
        self.embedding_dimension = embedding_dimension
        self.similarity_threshold = similarity_threshold
        self.persist_path = persist_path
        
        self._cache: OrderedDict[str, EmbeddingVector] = OrderedDict()
        self._hash_index: Dict[str, str] = {}  # screenshot_hash -> cache_key
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "similarity_matches": 0
        }
        
        # Load from persistent storage if available
        if persist_path and persist_path.exists():
            self._load_from_disk()
    
    def _compute_perceptual_hash(self, screenshot: bytes) -> str:
        """
        Compute perceptual hash of screenshot.
        
        Uses a simplified approach that captures visual characteristics.
        """
        # Simple hash based on image statistics
        # In production, would use proper perceptual hashing like pHash
        h = hashlib.md5()
        
        # Sample bytes at regular intervals for perceptual characteristics
        step = max(1, len(screenshot) // 1000)
        samples = screenshot[::step]
        h.update(samples)
        
        # Add length-based component for size characteristics
        h.update(struct.pack("I", len(screenshot)))
        
        return h.hexdigest()
    
    def _generate_simple_embedding(self, screenshot: bytes) -> List[float]:
        """
        Generate a simple embedding vector from screenshot.
        
        In production, this would use a vision model like CLIP or ResNet.
        This implementation creates a deterministic hash-based embedding.
        """
        # Create embedding from screenshot characteristics
        h = hashlib.sha256(screenshot)
        
        # Generate embedding values from hash
        hash_bytes = h.digest()
        embedding = []
        
        for i in range(self.embedding_dimension):
            # Use modulo to cycle through hash bytes
            byte_val = hash_bytes[i % len(hash_bytes)]
            # Normalize to [-1, 1] range
            val = (byte_val / 128.0) - 1.0
            embedding.append(val)
        
        return embedding
    
    def get_or_create_embedding(
        self,
        screenshot: bytes,
        compute_fn: Optional[Callable[[], List[float]]] = None
    ) -> Tuple[EmbeddingVector, bool]:
        """
        Get cached embedding or create new one.
        
        Args:
            screenshot: Screenshot bytes
            compute_fn: Optional function to compute embedding
            
        Returns:
            Tuple of (embedding, was_cached)
        """
        screenshot_hash = self._compute_perceptual_hash(screenshot)
        
        # Check cache
        if screenshot_hash in self._hash_index:
            cache_key = self._hash_index[screenshot_hash]
            if cache_key in self._cache:
                embedding = self._cache[cache_key]
                self._cache.move_to_end(cache_key)
                self._stats["hits"] += 1
                return embedding, True
        
        # Check for similar embeddings
        if compute_fn is None:
            compute_fn = lambda: self._generate_simple_embedding(screenshot)
        
        new_embedding_vector = compute_fn()
        new_embedding = EmbeddingVector(
            vector=new_embedding_vector,
            dimension=self.embedding_dimension,
            source_hash=screenshot_hash
        )
        
        # Check for similar existing embeddings
        for key, existing in self._cache.items():
            similarity = new_embedding.cosine_similarity(existing)
            if similarity >= self.similarity_threshold:
                self._stats["similarity_matches"] += 1
                self._cache.move_to_end(key)
                self._stats["hits"] += 1
                return existing, True
        
        # Create new entry
        self._stats["misses"] += 1
        self._add_to_cache(screenshot_hash, new_embedding)
        
        return new_embedding, False
    
    def _add_to_cache(self, screenshot_hash: str, embedding: EmbeddingVector):
        """Add embedding to cache with eviction if needed."""
        # Evict if at capacity
        while len(self._cache) >= self.max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            # Clean up hash index
            self._hash_index = {
                k: v for k, v in self._hash_index.items()
                if v != oldest_key
            }
            self._stats["evictions"] += 1
        
        cache_key = f"emb_{screenshot_hash}_{time.time()}"
        self._cache[cache_key] = embedding
        self._hash_index[screenshot_hash] = cache_key
    
    def find_similar(
        self,
        embedding: EmbeddingVector,
        top_k: int = 5,
        threshold: float = 0.8
    ) -> List[Tuple[str, float, EmbeddingVector]]:
        """
        Find similar embeddings in cache.
        
        Args:
            embedding: Query embedding
            top_k: Maximum number of results
            threshold: Minimum similarity threshold
            
        Returns:
            List of (key, similarity, embedding) tuples
        """
        results = []
        
        for key, cached_emb in self._cache.items():
            similarity = embedding.cosine_similarity(cached_emb)
            if similarity >= threshold:
                results.append((key, similarity, cached_emb))
        
        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0
        
        return {
            **self._stats,
            "size": len(self._cache),
            "max_size": self.max_size,
            "hit_rate": hit_rate,
        }
    
    def save_to_disk(self):
        """Save cache to disk."""
        if not self.persist_path:
            return
        
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "embeddings": [
                (key, emb.to_bytes()) for key, emb in self._cache.items()
            ],
            "hash_index": self._hash_index,
            "stats": self._stats,
        }
        
        with open(self.persist_path, "wb") as f:
            pickle.dump(data, f)
        
        logger.info(f"Saved {len(self._cache)} embeddings to disk")
    
    def _load_from_disk(self):
        """Load cache from disk."""
        if not self.persist_path or not self.persist_path.exists():
            return
        
        try:
            with open(self.persist_path, "rb") as f:
                data = pickle.load(f)
            
            for key, emb_bytes in data.get("embeddings", []):
                self._cache[key] = EmbeddingVector.from_bytes(emb_bytes)
            
            self._hash_index = data.get("hash_index", {})
            self._stats = data.get("stats", self._stats)
            
            logger.info(f"Loaded {len(self._cache)} embeddings from disk")
        except Exception as e:
            logger.warning(f"Failed to load embeddings from disk: {e}")
    
    def clear(self):
        """Clear the cache."""
        self._cache.clear()
        self._hash_index.clear()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "similarity_matches": 0
        }


# ============================================================================
# UI State Detector
# ============================================================================

class UIStateDetector:
    """
    Detects and tracks similar UI states.
    
    Features:
    - State fingerprinting using embeddings
    - Similar state detection
    - State transition tracking
    - Visit counting
    """
    
    def __init__(
        self,
        embedding_cache: ScreenshotEmbeddingCache,
        state_similarity_threshold: float = 0.85,
        max_states: int = 500
    ):
        """
        Initialize UI state detector.
        
        Args:
            embedding_cache: Cache for screenshot embeddings
            state_similarity_threshold: Threshold for state similarity
            max_states: Maximum number of states to track
        """
        self.embedding_cache = embedding_cache
        self.state_similarity_threshold = state_similarity_threshold
        self.max_states = max_states
        
        self._states: Dict[str, UIState] = {}
        self._url_state_index: Dict[str, List[str]] = {}  # URL -> state IDs
        self._state_transitions: Dict[str, List[str]] = {}  # state_id -> [target_state_ids]
    
    def detect_state(
        self,
        screenshot: bytes,
        url: str,
        title: str = "",
        element_count: int = 0,
        interactive_count: int = 0
    ) -> Tuple[UIState, bool]:
        """
        Detect UI state from screenshot.
        
        Args:
            screenshot: Screenshot bytes
            url: Current page URL
            title: Page title
            element_count: Total element count
            interactive_count: Interactive element count
            
        Returns:
            Tuple of (state, is_new)
        """
        # Get embedding
        embedding, was_cached = self.embedding_cache.get_or_create_embedding(screenshot)
        
        # Compute state hash
        screenshot_hash = hashlib.md5(screenshot).hexdigest()
        
        # Check for similar existing states
        similar_states = self._find_similar_states(embedding, url)
        
        if similar_states:
            # Return most similar state
            best_state = similar_states[0]
            best_state.visit_count += 1
            best_state.last_visit = time.time()
            return best_state, False
        
        # Create new state
        state_id = f"state_{hashlib.md5(f'{url}_{screenshot_hash}'.encode()).hexdigest()[:12]}"
        
        new_state = UIState(
            state_id=state_id,
            embedding=embedding,
            url=url,
            title=title,
            element_count=element_count,
            interactive_count=interactive_count,
            screenshot_hash=screenshot_hash
        )
        
        # Add to tracking
        self._add_state(new_state)
        
        return new_state, True
    
    def _find_similar_states(
        self,
        embedding: EmbeddingVector,
        url: Optional[str] = None
    ) -> List[UIState]:
        """Find states similar to given embedding."""
        candidates = []
        
        # If URL provided, check states with same URL first
        if url and url in self._url_state_index:
            for state_id in self._url_state_index[url]:
                if state_id in self._states:
                    candidates.append(self._states[state_id])
        
        # Also check all states if not enough candidates
        if len(candidates) < 5:
            candidates = list(self._states.values())
        
        # Calculate similarities
        similar = []
        for state in candidates:
            similarity = embedding.cosine_similarity(state.embedding)
            if similarity >= self.state_similarity_threshold:
                similar.append((state, similarity))
        
        # Sort by similarity
        similar.sort(key=lambda x: x[1], reverse=True)
        
        return [s[0] for s in similar]
    
    def _add_state(self, state: UIState):
        """Add state to tracking."""
        # Evict oldest if at capacity
        if len(self._states) >= self.max_states:
            oldest_id = min(
                self._states.keys(),
                key=lambda x: self._states[x].last_visit
            )
            self._remove_state(oldest_id)
        
        self._states[state.state_id] = state
        
        # Update URL index
        if state.url not in self._url_state_index:
            self._url_state_index[state.url] = []
        self._url_state_index[state.url].append(state.state_id)
    
    def _remove_state(self, state_id: str):
        """Remove state from tracking."""
        if state_id not in self._states:
            return
        
        state = self._states[state_id]
        
        # Remove from URL index
        if state.url in self._url_state_index:
            self._url_state_index[state.url] = [
                s for s in self._url_state_index[state.url] if s != state_id
            ]
        
        del self._states[state_id]
    
    def record_transition(self, from_state_id: str, to_state_id: str):
        """Record state transition."""
        if from_state_id not in self._state_transitions:
            self._state_transitions[from_state_id] = []
        
        if to_state_id not in self._state_transitions[from_state_id]:
            self._state_transitions[from_state_id].append(to_state_id)
    
    def record_action(self, state_id: str, action: str, outcome: str):
        """Record action taken in state."""
        if state_id in self._states:
            state = self._states[state_id]
            state.actions_taken.append(action)
            state.outcomes.append(outcome)
    
    def get_state(self, state_id: str) -> Optional[UIState]:
        """Get state by ID."""
        return self._states.get(state_id)
    
    def get_states_for_url(self, url: str) -> List[UIState]:
        """Get all states for a URL."""
        if url not in self._url_state_index:
            return []
        return [
            self._states[sid] for sid in self._url_state_index[url]
            if sid in self._states
        ]
    
    def get_transition_targets(self, state_id: str) -> List[str]:
        """Get possible transition targets from a state."""
        return self._state_transitions.get(state_id, [])
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics."""
        total_visits = sum(s.visit_count for s in self._states.values())
        avg_actions = (
            sum(len(s.actions_taken) for s in self._states.values()) / len(self._states)
            if self._states else 0
        )
        
        return {
            "total_states": len(self._states),
            "max_states": self.max_states,
            "total_visits": total_visits,
            "unique_urls": len(self._url_state_index),
            "total_transitions": sum(
                len(targets) for targets in self._state_transitions.values()
            ),
            "avg_actions_per_state": avg_actions,
        }


# ============================================================================
# Navigation Pattern Learner
# ============================================================================

class NavigationPatternLearner:
    """
    Learns and applies navigation patterns.
    
    Features:
    - Pattern extraction from successful navigations
    - Pattern matching for similar situations
    - Success rate tracking
    - Pattern optimization
    """
    
    def __init__(
        self,
        max_patterns: int = 200,
        min_success_rate: float = 0.6,
        pattern_similarity_threshold: float = 0.8
    ):
        """
        Initialize navigation pattern learner.
        
        Args:
            max_patterns: Maximum patterns to store
            min_success_rate: Minimum success rate to keep pattern
            pattern_similarity_threshold: Threshold for pattern matching
        """
        self.max_patterns = max_patterns
        self.min_success_rate = min_success_rate
        self.pattern_similarity_threshold = pattern_similarity_threshold
        
        self._patterns: Dict[str, NavigationPattern] = {}
        self._source_index: Dict[str, List[str]] = {}  # source_state -> pattern_ids
        self._target_index: Dict[str, List[str]] = {}  # target_state -> pattern_ids
    
    def learn_pattern(
        self,
        source_state: UIState,
        target_state: UIState,
        action_sequence: List[Dict[str, Any]],
        duration: float,
        success: bool
    ) -> Optional[NavigationPattern]:
        """
        Learn navigation pattern from execution.
        
        Args:
            source_state: Starting state
            target_state: Ending state
            action_sequence: Actions taken
            duration: Navigation duration
            success: Whether navigation succeeded
            
        Returns:
            Created or updated pattern, or None if not learnable
        """
        if not action_sequence:
            return None
        
        # Check for existing similar pattern
        existing_pattern = self._find_similar_pattern(
            source_state.state_id,
            target_state.state_id,
            action_sequence
        )
        
        if existing_pattern:
            existing_pattern.record_outcome(success, duration)
            return existing_pattern
        
        # Create new pattern
        pattern_id = f"pattern_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        
        new_pattern = NavigationPattern(
            pattern_id=pattern_id,
            source_state_id=source_state.state_id,
            target_state_id=target_state.state_id,
            action_sequence=action_sequence.copy()
        )
        new_pattern.record_outcome(success, duration)
        
        self._add_pattern(new_pattern)
        
        return new_pattern
    
    def _find_similar_pattern(
        self,
        source_state_id: str,
        target_state_id: str,
        action_sequence: List[Dict[str, Any]]
    ) -> Optional[NavigationPattern]:
        """Find similar existing pattern."""
        # Check patterns with same source/target first
        candidates = []
        
        if source_state_id in self._source_index:
            for pattern_id in self._source_index[source_state_id]:
                if pattern_id in self._patterns:
                    pattern = self._patterns[pattern_id]
                    if pattern.target_state_id == target_state_id:
                        candidates.append(pattern)
        
        # Check action sequence similarity
        for pattern in candidates:
            if self._action_sequences_similar(
                action_sequence,
                pattern.action_sequence
            ):
                return pattern
        
        return None
    
    def _action_sequences_similar(
        self,
        seq1: List[Dict[str, Any]],
        seq2: List[Dict[str, Any]]
    ) -> bool:
        """Check if two action sequences are similar."""
        if len(seq1) != len(seq2):
            return False
        
        for a1, a2 in zip(seq1, seq2):
            if a1.get("type") != a2.get("type"):
                return False
            
            # Check selector similarity for element actions
            s1 = a1.get("selector", "")
            s2 = a2.get("selector", "")
            if s1 and s2 and s1 != s2:
                # Allow some flexibility in selectors
                if not (s1 in s2 or s2 in s1):
                    return False
        
        return True
    
    def _add_pattern(self, pattern: NavigationPattern):
        """Add pattern to storage."""
        # Evict low success rate patterns if at capacity
        if len(self._patterns) >= self.max_patterns:
            self._evict_worst_pattern()
        
        self._patterns[pattern.pattern_id] = pattern
        
        # Update indices
        if pattern.source_state_id not in self._source_index:
            self._source_index[pattern.source_state_id] = []
        self._source_index[pattern.source_state_id].append(pattern.pattern_id)
        
        if pattern.target_state_id not in self._target_index:
            self._target_index[pattern.target_state_id] = []
        self._target_index[pattern.target_state_id].append(pattern.pattern_id)
    
    def _evict_worst_pattern(self):
        """Evict pattern with lowest success rate."""
        if not self._patterns:
            return
        
        worst_id = min(
            self._patterns.keys(),
            key=lambda x: self._patterns[x].success_rate
        )
        
        pattern = self._patterns[worst_id]
        
        # Remove from indices
        if pattern.source_state_id in self._source_index:
            self._source_index[pattern.source_state_id] = [
                p for p in self._source_index[pattern.source_state_id]
                if p != worst_id
            ]
        if pattern.target_state_id in self._target_index:
            self._target_index[pattern.target_state_id] = [
                p for p in self._target_index[pattern.target_state_id]
                if p != worst_id
            ]
        
        del self._patterns[worst_id]
    
    def get_patterns_for_source(self, source_state_id: str) -> List[NavigationPattern]:
        """Get patterns starting from a state."""
        if source_state_id not in self._source_index:
            return []
        
        patterns = [
            self._patterns[pid]
            for pid in self._source_index[source_state_id]
            if pid in self._patterns
        ]
        
        # Sort by success rate
        return sorted(patterns, key=lambda p: p.success_rate, reverse=True)
    
    def get_patterns_for_target(self, target_state_id: str) -> List[NavigationPattern]:
        """Get patterns ending at a state."""
        if target_state_id not in self._target_index:
            return []
        
        patterns = [
            self._patterns[pid]
            for pid in self._target_index[target_state_id]
            if pid in self._patterns
        ]
        
        return sorted(patterns, key=lambda p: p.success_rate, reverse=True)
    
    def suggest_navigation(
        self,
        source_state: UIState,
        target_url: Optional[str] = None
    ) -> List[Tuple[NavigationPattern, float]]:
        """
        Suggest navigation patterns for current state.
        
        Args:
            source_state: Current state
            target_url: Optional target URL
            
        Returns:
            List of (pattern, confidence) tuples
        """
        suggestions = []
        
        for pattern in self.get_patterns_for_source(source_state.state_id):
            if pattern.success_rate < self.min_success_rate:
                continue
            
            confidence = pattern.success_rate
            
            # Boost confidence for frequently used patterns
            total_uses = pattern.success_count + pattern.failure_count
            if total_uses > 5:
                confidence *= 1.1
            if total_uses > 10:
                confidence *= 1.1
            
            suggestions.append((pattern, min(confidence, 1.0)))
        
        return sorted(suggestions, key=lambda x: x[1], reverse=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get learner statistics."""
        if not self._patterns:
            return {
                "total_patterns": 0,
                "avg_success_rate": 0,
                "total_uses": 0,
            }
        
        return {
            "total_patterns": len(self._patterns),
            "max_patterns": self.max_patterns,
            "avg_success_rate": sum(
                p.success_rate for p in self._patterns.values()
            ) / len(self._patterns),
            "total_uses": sum(
                p.success_count + p.failure_count for p in self._patterns.values()
            ),
        }


# ============================================================================
# Dynamic Element Reidentifier
# ============================================================================

class DynamicElementReidentifier:
    """
    Fast re-identification of dynamic elements.
    
    Features:
    - Element fingerprinting
    - Position tracking with variations
    - State association
    - Quick lookup by characteristics
    """
    
    def __init__(
        self,
        max_elements: int = 1000,
        position_tolerance: int = 20
    ):
        """
        Initialize element reidentifier.
        
        Args:
            max_elements: Maximum elements to track
            position_tolerance: Pixel tolerance for position matching
        """
        self.max_elements = max_elements
        self.position_tolerance = position_tolerance
        
        self._elements: Dict[str, DynamicElement] = {}
        self._selector_index: Dict[str, str] = {}  # selector -> element_id
        self._content_index: Dict[str, List[str]] = {}  # content_hash -> element_ids
    
    def track_element(
        self,
        selector: str,
        content: str,
        position: Tuple[int, int, int, int],
        element_type: str,
        state_id: Optional[str] = None
    ) -> DynamicElement:
        """
        Track or re-identify an element.
        
        Args:
            selector: Element selector
            content: Element content/text
            position: Element position (x, y, width, height)
            element_type: Type of element
            state_id: Associated state ID
            
        Returns:
            Tracked element
        """
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        # Check for existing element by selector
        if selector in self._selector_index:
            element_id = self._selector_index[selector]
            if element_id in self._elements:
                element = self._elements[element_id]
                element.update_position(position)
                if state_id and state_id not in element.state_associations:
                    element.state_associations.append(state_id)
                return element
        
        # Check for similar element by content and position
        if content_hash in self._content_index:
            for existing_id in self._content_index[content_hash]:
                if existing_id in self._elements:
                    existing = self._elements[existing_id]
                    if self._positions_similar(existing.position, position):
                        existing.update_position(position)
                        if state_id and state_id not in existing.state_associations:
                            existing.state_associations.append(state_id)
                        return existing
        
        # Create new element
        element_id = f"elem_{hashlib.md5(f'{selector}_{time.time()}'.encode()).hexdigest()[:8]}"
        
        new_element = DynamicElement(
            element_id=element_id,
            selector=selector,
            content_hash=content_hash,
            position=position,
            element_type=element_type
        )
        
        if state_id:
            new_element.state_associations.append(state_id)
        
        self._add_element(new_element)
        
        return new_element
    
    def _positions_similar(
        self,
        pos1: Tuple[int, int, int, int],
        pos2: Tuple[int, int, int, int]
    ) -> bool:
        """Check if positions are similar within tolerance."""
        for p1, p2 in zip(pos1, pos2):
            if abs(p1 - p2) > self.position_tolerance:
                return False
        return True
    
    def _add_element(self, element: DynamicElement):
        """Add element to tracking."""
        # Evict oldest if at capacity
        if len(self._elements) >= self.max_elements:
            oldest_id = min(
                self._elements.keys(),
                key=lambda x: self._elements[x].last_seen
            )
            self._remove_element(oldest_id)
        
        self._elements[element.element_id] = element
        self._selector_index[element.selector] = element.element_id
        
        if element.content_hash not in self._content_index:
            self._content_index[element.content_hash] = []
        self._content_index[element.content_hash].append(element.element_id)
    
    def _remove_element(self, element_id: str):
        """Remove element from tracking."""
        if element_id not in self._elements:
            return
        
        element = self._elements[element_id]
        
        # Remove from indices
        if element.selector in self._selector_index:
            del self._selector_index[element.selector]
        
        if element.content_hash in self._content_index:
            self._content_index[element.content_hash] = [
                eid for eid in self._content_index[element.content_hash]
                if eid != element_id
            ]
        
        del self._elements[element_id]
    
    def find_by_selector(self, selector: str) -> Optional[DynamicElement]:
        """Find element by selector."""
        if selector in self._selector_index:
            return self._elements.get(self._selector_index[selector])
        return None
    
    def find_by_content(self, content: str) -> List[DynamicElement]:
        """Find elements by content."""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        if content_hash not in self._content_index:
            return []
        
        return [
            self._elements[eid]
            for eid in self._content_index[content_hash]
            if eid in self._elements
        ]
    
    def find_by_position(
        self,
        position: Tuple[int, int, int, int]
    ) -> List[DynamicElement]:
        """Find elements near a position."""
        results = []
        
        for element in self._elements.values():
            if self._positions_similar(element.position, position):
                results.append(element)
        
        return results
    
    def get_elements_for_state(self, state_id: str) -> List[DynamicElement]:
        """Get all elements associated with a state."""
        return [
            e for e in self._elements.values()
            if state_id in e.state_associations
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get reidentifier statistics."""
        if not self._elements:
            return {
                "total_elements": 0,
                "avg_appearances": 0,
                "elements_with_variations": 0,
            }
        
        return {
            "total_elements": len(self._elements),
            "max_elements": self.max_elements,
            "avg_appearances": sum(
                e.appearance_count for e in self._elements.values()
            ) / len(self._elements),
            "elements_with_variations": sum(
                1 for e in self._elements.values() if e.position_variations
            ),
        }


# ============================================================================
# Visual Memory System (Main Coordinator)
# ============================================================================

class VisualMemorySystem:
    """
    Main visual memory system coordinating all components.
    
    Features:
    - Screenshot embedding cache
    - UI state detection
    - Navigation pattern learning
    - Dynamic element re-identification
    """
    
    def __init__(
        self,
        embedding_cache: Optional[ScreenshotEmbeddingCache] = None,
        state_detector: Optional[UIStateDetector] = None,
        pattern_learner: Optional[NavigationPatternLearner] = None,
        element_reidentifier: Optional[DynamicElementReidentifier] = None,
        persist_path: Optional[Path] = None
    ):
        """
        Initialize visual memory system.
        
        Args:
            embedding_cache: Optional custom embedding cache
            state_detector: Optional custom state detector
            pattern_learner: Optional custom pattern learner
            element_reidentifier: Optional custom element reidentifier
            persist_path: Path for persistent storage
        """
        self.persist_path = persist_path
        
        # Initialize components
        self.embedding_cache = embedding_cache or ScreenshotEmbeddingCache(
            persist_path=persist_path / "embeddings.pkl" if persist_path else None
        )
        self.state_detector = state_detector or UIStateDetector(
            embedding_cache=self.embedding_cache
        )
        self.pattern_learner = pattern_learner or NavigationPatternLearner()
        self.element_reidentifier = element_reidentifier or DynamicElementReidentifier()
        
        self._current_state: Optional[UIState] = None
        self._navigation_start_time: Optional[float] = None
        self._current_action_sequence: List[Dict[str, Any]] = []
    
    def process_screenshot(
        self,
        screenshot: bytes,
        url: str,
        title: str = "",
        element_count: int = 0,
        interactive_count: int = 0
    ) -> Tuple[UIState, bool]:
        """
        Process screenshot and detect UI state.
        
        Args:
            screenshot: Screenshot bytes
            url: Current URL
            title: Page title
            element_count: Total elements on page
            interactive_count: Interactive elements count
            
        Returns:
            Tuple of (state, is_new_state)
        """
        state, is_new = self.state_detector.detect_state(
            screenshot=screenshot,
            url=url,
            title=title,
            element_count=element_count,
            interactive_count=interactive_count
        )
        
        # Record transition from previous state
        if self._current_state and self._current_state.state_id != state.state_id:
            self.state_detector.record_transition(
                self._current_state.state_id,
                state.state_id
            )
        
        self._current_state = state
        
        return state, is_new
    
    def start_navigation(self):
        """Start navigation tracking."""
        self._navigation_start_time = time.time()
        self._current_action_sequence = []
    
    def record_action(self, action: Dict[str, Any]):
        """Record action during navigation."""
        self._current_action_sequence.append(action)
        
        if self._current_state:
            action_str = f"{action.get('type', 'unknown')}:{action.get('selector', '')}"
            self.state_detector.record_action(
                self._current_state.state_id,
                action_str,
                "pending"
            )
    
    def end_navigation(self, success: bool, target_state: Optional[UIState] = None):
        """End navigation and learn pattern."""
        if not self._navigation_start_time:
            return
        
        duration = time.time() - self._navigation_start_time
        
        # Update action outcomes
        if self._current_state:
            for i, action in enumerate(self._current_action_sequence):
                action_str = f"{action.get('type', 'unknown')}:{action.get('selector', '')}"
                # Update last occurrence of this action
                state = self._current_state
                if action_str in state.actions_taken:
                    idx = len(state.actions_taken) - 1 - state.actions_taken[::-1].index(action_str)
                    state.outcomes[idx] = "success" if success else "failure"
        
        # Learn pattern if we have states and actions
        if (self._current_state and target_state and 
            self._current_action_sequence):
            self.pattern_learner.learn_pattern(
                source_state=self._current_state,
                target_state=target_state,
                action_sequence=self._current_action_sequence,
                duration=duration,
                success=success
            )
        
        self._navigation_start_time = None
        self._current_action_sequence = []
    
    def track_element(
        self,
        selector: str,
        content: str,
        position: Tuple[int, int, int, int],
        element_type: str
    ) -> DynamicElement:
        """Track a dynamic element."""
        state_id = self._current_state.state_id if self._current_state else None
        return self.element_reidentifier.track_element(
            selector=selector,
            content=content,
            position=position,
            element_type=element_type,
            state_id=state_id
        )
    
    def get_navigation_suggestions(self) -> List[Tuple[NavigationPattern, float]]:
        """Get navigation suggestions for current state."""
        if not self._current_state:
            return []
        return self.pattern_learner.suggest_navigation(self._current_state)
    
    def get_similar_states(self, screenshot: bytes) -> List[UIState]:
        """Find states similar to screenshot."""
        embedding, _ = self.embedding_cache.get_or_create_embedding(screenshot)
        return self.state_detector._find_similar_states(embedding)
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics from all components."""
        return {
            "embedding_cache": self.embedding_cache.get_stats(),
            "state_detector": self.state_detector.get_stats(),
            "pattern_learner": self.pattern_learner.get_stats(),
            "element_reidentifier": self.element_reidentifier.get_stats(),
        }
    
    def save_state(self):
        """Save all state to disk."""
        if self.persist_path:
            self.persist_path.mkdir(parents=True, exist_ok=True)
            self.embedding_cache.save_to_disk()
            logger.info("Visual memory state saved")
    
    def clear(self):
        """Clear all memory."""
        self.embedding_cache.clear()
        self._current_state = None
        self._navigation_start_time = None
        self._current_action_sequence = []
        logger.info("Visual memory cleared")
