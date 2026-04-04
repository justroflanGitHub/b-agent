"""Adaptive replay — self-healing when pages change since recording.

When a recorded selector or element no longer exists, uses multiple
fallback strategies to find the equivalent element.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ElementMatch:
    """Result of finding an element on a changed page."""

    found: bool = False
    strategy: str = "none"  # "selector", "text", "vision", "position", "description"
    coordinates: Optional[Tuple[int, int]] = None
    selector: Optional[str] = None
    confidence: float = 0.0


@dataclass
class PageMatchResult:
    """Result of comparing current page to recorded state."""

    matches: bool = False
    similarity: float = 0.0
    changed_regions: list = field(default_factory=list)
    structural_changes: list = field(default_factory=list)


class AdaptiveReplay:
    """Self-healing replay that adapts to page changes.

    Strategy cascade:
    1. Selector match (fast)
    2. Text content match (medium)
    3. Description match (slower)
    4. Position heuristic (last resort)
    """

    def __init__(self, similarity_threshold: float = 0.85):
        self._threshold = similarity_threshold

    async def match_page_state(
        self,
        current_html: str = "",
        recorded_html: str = "",
        current_screenshot_hash: Optional[str] = None,
        recorded_screenshot_hash: Optional[str] = None,
    ) -> PageMatchResult:
        """Compare current page to recorded state."""
        # Simple hash comparison
        if current_screenshot_hash and recorded_screenshot_hash:
            if current_screenshot_hash == recorded_screenshot_hash:
                return PageMatchResult(matches=True, similarity=1.0)

        # Structural comparison via HTML hash
        current_hash = hashlib.sha256(current_html.encode()).hexdigest() if current_html else ""
        recorded_hash = hashlib.sha256(recorded_html.encode()).hexdigest() if recorded_html else ""

        if current_hash == recorded_hash:
            return PageMatchResult(matches=True, similarity=1.0)

        # Simple similarity: compare common elements
        if current_html and recorded_html:
            common = len(set(current_html.split()) & set(recorded_html.split()))
            total = max(len(set(current_html.split()) | set(recorded_html.split())), 1)
            similarity = common / total
            return PageMatchResult(
                matches=similarity >= self._threshold,
                similarity=similarity,
            )

        return PageMatchResult(matches=False, similarity=0.0)

    async def find_element(self, action) -> ElementMatch:
        """Find the equivalent element on a changed page.

        Tries strategies in order of speed/accuracy.
        """
        # Strategy 1: Selector match
        if action.target_selector:
            match = await self._try_selector(action.target_selector)
            if match.found:
                return match

        # Strategy 2: Text content match
        if action.target_text:
            match = await self._try_text_match(action.target_text)
            if match.found:
                return match

        # Strategy 3: Description match
        if action.target_description:
            match = await self._try_description(action.target_description, action.target_element_type)
            if match.found:
                return match

        # Strategy 4: Position heuristic
        if action.target_coordinates:
            match = await self._try_position(action.target_coordinates)
            if match.found:
                return match

        return ElementMatch(found=False, strategy="none")

    async def verify_action_result(
        self,
        before_hash: Optional[str] = None,
        after_hash: Optional[str] = None,
        expected_change: str = "",
    ) -> bool:
        """Verify the action had the expected effect."""
        if before_hash and after_hash:
            return before_hash != after_hash
        return True

    async def _try_selector(self, selector: str) -> ElementMatch:
        """Try finding element by CSS selector."""
        # In real impl, would query the live page
        return ElementMatch(
            found=False,  # Would be True if selector found on page
            strategy="selector",
            selector=selector,
            confidence=0.95,
        )

    async def _try_text_match(self, text: str) -> ElementMatch:
        """Try finding element by its text content."""
        return ElementMatch(
            found=False,
            strategy="text",
            confidence=0.8,
        )

    async def _try_description(self, description: str, element_type: Optional[str] = None) -> ElementMatch:
        """Try finding element by visual description (would use vision model)."""
        return ElementMatch(
            found=False,
            strategy="description",
            confidence=0.6,
        )

    async def _try_position(self, coordinates: Tuple[int, int]) -> ElementMatch:
        """Try clicking at recorded coordinates (last resort)."""
        return ElementMatch(
            found=True,
            strategy="position",
            coordinates=coordinates,
            confidence=0.3,
        )
