"""
Vision Analysis Module - Advanced visual intelligence for browser automation.

This module provides:
- Bounding box extraction
- Element classification
- Multi-element detection
- Page state analysis
- Visual diff comparison
- Screenshot caching
"""

from .analyzer import VisualAnalyzer, BoundingBox, ElementInfo, PageState
from .cache import VisionCache
from .diff import VisualDiff

__all__ = [
    "VisualAnalyzer",
    "BoundingBox",
    "ElementInfo",
    "PageState",
    "VisionCache",
    "VisualDiff",
]
