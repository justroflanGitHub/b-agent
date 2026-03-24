"""
Visual Diff - Screenshot comparison for change detection.

Provides:
- Pixel-wise screenshot comparison
- Visual diff generation
- Change region detection
- Similarity scoring
"""

import base64
import hashlib
import io
import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import PIL for image processing
try:
    from PIL import Image
    import numpy as np
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("PIL/Numpy not available, visual diff will use basic comparison")


@dataclass
class DiffRegion:
    """Region with detected changes."""
    x: int
    y: int
    width: int
    height: int
    change_percentage: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "change_percentage": self.change_percentage
        }


@dataclass
class VisualDiffResult:
    """Result of visual diff comparison."""
    are_similar: bool
    similarity_score: float
    changed_regions: List[DiffRegion]
    diff_image_base64: Optional[str] = None
    total_pixels_changed: int = 0
    total_pixels: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "are_similar": self.are_similar,
            "similarity_score": self.similarity_score,
            "changed_regions": [r.to_dict() for r in self.changed_regions],
            "diff_image_base64": self.diff_image_base64,
            "total_pixels_changed": self.total_pixels_changed,
            "total_pixels": self.total_pixels
        }


class VisualDiff:
    """
    Visual diff tool for screenshot comparison.
    
    Features:
    - Pixel-wise comparison
    - Region-based change detection
    - Diff image generation
    - Configurable similarity threshold
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.95,
        change_threshold: float = 0.1,
        region_size: int = 50
    ):
        """
        Initialize visual diff.
        
        Args:
            similarity_threshold: Threshold for considering images similar (0.0-1.0)
            change_threshold: Threshold for detecting changed regions (0.0-1.0)
            region_size: Size of regions for change detection grid
        """
        self.similarity_threshold = similarity_threshold
        self.change_threshold = change_threshold
        self.region_size = region_size
    
    def compare(
        self,
        before: bytes,
        after: bytes
    ) -> VisualDiffResult:
        """
        Compare two screenshots.
        
        Args:
            before: Before screenshot (PNG bytes)
            after: After screenshot (PNG bytes)
            
        Returns:
            VisualDiffResult with comparison details
        """
        if not HAS_PIL:
            return self._basic_compare(before, after)
        
        try:
            # Load images
            before_img = Image.open(io.BytesIO(before))
            after_img = Image.open(io.BytesIO(after))
            
            # Ensure same size
            if before_img.size != after_img.size:
                logger.warning("Image sizes differ, resizing for comparison")
                after_img = after_img.resize(before_img.size)
            
            # Convert to RGB
            before_arr = np.array(before_img.convert("RGB"))
            after_arr = np.array(after_img.convert("RGB"))
            
            # Calculate pixel-wise difference
            diff = np.abs(before_arr.astype(float) - after_arr.astype(float))
            
            # Calculate similarity
            total_pixels = before_arr.shape[0] * before_arr.shape[1]
            max_diff = 255.0 * 3  # Max difference per pixel (R+G+B)
            
            # Normalize difference to 0-1
            normalized_diff = diff.sum(axis=2) / max_diff
            
            # Calculate similarity score
            mean_diff = normalized_diff.mean()
            similarity_score = 1.0 - mean_diff
            
            # Count changed pixels (> 5% difference)
            pixel_threshold = 0.05
            changed_mask = normalized_diff > pixel_threshold
            total_pixels_changed = changed_mask.sum()
            
            # Detect changed regions
            changed_regions = self._detect_regions(changed_mask, normalized_diff)
            
            # Generate diff image
            diff_image_base64 = self._generate_diff_image(before_arr, after_arr, diff)
            
            # Determine if similar
            are_similar = similarity_score >= self.similarity_threshold
            
            return VisualDiffResult(
                are_similar=are_similar,
                similarity_score=similarity_score,
                changed_regions=changed_regions,
                diff_image_base64=diff_image_base64,
                total_pixels_changed=int(total_pixels_changed),
                total_pixels=int(total_pixels)
            )
            
        except Exception as e:
            logger.error(f"Visual diff failed: {e}")
            return VisualDiffResult(
                are_similar=False,
                similarity_score=0.0,
                changed_regions=[],
                total_pixels_changed=0,
                total_pixels=0
            )
    
    def _basic_compare(self, before: bytes, after: bytes) -> VisualDiffResult:
        """Basic comparison without PIL."""
        before_hash = hashlib.md5(before).hexdigest()
        after_hash = hashlib.md5(after).hexdigest()
        
        are_similar = before_hash == after_hash
        similarity_score = 1.0 if are_similar else 0.0
        
        return VisualDiffResult(
            are_similar=are_similar,
            similarity_score=similarity_score,
            changed_regions=[],
            total_pixels_changed=0 if are_similar else 1,
            total_pixels=1
        )
    
    def _detect_regions(
        self,
        changed_mask: "np.ndarray",
        diff_values: "np.ndarray"
    ) -> List[DiffRegion]:
        """Detect regions with significant changes."""
        if not HAS_PIL:
            return []
        
        regions = []
        height, width = changed_mask.shape
        region_size = self.region_size
        
        # Grid-based region detection
        for y in range(0, height, region_size):
            for x in range(0, width, region_size):
                # Extract region
                y_end = min(y + region_size, height)
                x_end = min(x + region_size, width)
                region_mask = changed_mask[y:y_end, x:x_end]
                
                # Calculate change percentage in region
                region_total = region_mask.size
                region_changed = region_mask.sum()
                change_pct = region_changed / region_total if region_total > 0 else 0
                
                if change_pct > self.change_threshold:
                    regions.append(DiffRegion(
                        x=int(x),
                        y=int(y),
                        width=int(x_end - x),
                        height=int(y_end - y),
                        change_percentage=float(change_pct)
                    ))
        
        return regions
    
    def _generate_diff_image(
        self,
        before: "np.ndarray",
        after: "np.ndarray",
        diff: "np.ndarray"
    ) -> Optional[str]:
        """Generate diff visualization image."""
        if not HAS_PIL:
            return None
        
        try:
            # Create diff visualization
            # Red channel shows differences
            diff_vis = after.copy()
            
            # Normalize diff for visualization
            max_diff = 255.0 * 3
            diff_intensity = (diff.sum(axis=2) / max_diff * 255).astype(np.uint8)
            
            # Highlight changed areas in red
            changed_mask = diff_intensity > 12  # ~5% threshold
            diff_vis[changed_mask] = [255, 0, 0]  # Red for changes
            
            # Blend with original
            alpha = 0.3
            result = (after * (1 - alpha) + diff_vis * alpha).astype(np.uint8)
            
            # Convert to base64
            img = Image.fromarray(result)
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
            
        except Exception as e:
            logger.error(f"Failed to generate diff image: {e}")
            return None
    
    def quick_compare(self, before: bytes, after: bytes) -> bool:
        """
        Quick comparison to check if images are similar.
        
        Args:
            before: Before screenshot (PNG bytes)
            after: After screenshot (PNG bytes)
            
        Returns:
            True if images are similar, False otherwise
        """
        result = self.compare(before, after)
        return result.are_similar
    
    def get_similarity_score(self, before: bytes, after: bytes) -> float:
        """
        Get similarity score between two screenshots.
        
        Args:
            before: Before screenshot (PNG bytes)
            after: After screenshot (PNG bytes)
            
        Returns:
            Similarity score (0.0-1.0)
        """
        result = self.compare(before, after)
        return result.similarity_score


def create_visual_diff(
    similarity_threshold: float = 0.95,
    change_threshold: float = 0.1
) -> VisualDiff:
    """Create a visual diff instance with specified thresholds."""
    return VisualDiff(
        similarity_threshold=similarity_threshold,
        change_threshold=change_threshold
    )
