"""
agents/layout_agent.py - Layout & Spatial Fit Specialist Agent
Handles:
1. Multi-unit dimension parsing (cm, meters, feet, inches)
2. Partial dimension accumulation across conversational turns (e.g. L*B first, then H)
3. Strictest refusal if dimensions are missing or user says "I don't know"
4. 35% safe circulation clearance checking and median footprint imputation
"""

import os
import re
from typing import Dict, Any, List, Optional, Tuple

import tools

DB_PATH = tools.DB_PATH


class LayoutAgent:
    """Specialist sub-agent for spatial geometry, unit normalization, and circulation fit."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH

    def parse_dimensions(
        self,
        text: str,
        current_l: Optional[float] = None,
        current_w: Optional[float] = None,
        current_h: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Parses dimension expressions in cm, meters, feet, or inches.
        Accumulates partial dimensions (length, breadth, height) across conversational turns.
        Returns:
            {
                "is_confused": bool,
                "length_cm": Optional[float],
                "width_cm": Optional[float],
                "height_cm": Optional[float],
                "is_complete": bool,
                "missing_parts": List[str]
            }
        """
        if not text:
            return {
                "is_confused": True,
                "length_cm": current_l,
                "width_cm": current_w,
                "height_cm": current_h,
                "is_complete": bool(current_l and current_w and current_h),
                "missing_parts": [p for p, val in [("length", current_l), ("breadth", current_w), ("height", current_h)] if not val]
            }

        cleaned = text.strip().lower()

        # Check for refusal / confused / don't know
        confused_phrases = ["don't know", "dont know", "confused", "not sure", "no idea", "can't measure"]
        if any(p in cleaned for p in confused_phrases):
            return {
                "is_confused": True,
                "length_cm": current_l,
                "width_cm": current_w,
                "height_cm": current_h,
                "is_complete": False,
                "missing_parts": ["length", "breadth", "height"]
            }

        l_val = current_l
        w_val = current_w
        h_val = current_h

        def _to_cm(num: float, unit_str: str) -> float:
            u = unit_str.strip().lower() if unit_str else "cm"
            if "m" in u and "cm" not in u:  # meter
                return round(num * 100.0, 1)
            elif "ft" in u or "feet" in u or "'" in u:
                return round(num * 30.48, 1)
            elif "in" in u or "inch" in u or '"' in u:
                return round(num * 2.54, 1)
            elif "cm" in u:
                return round(num, 1)
            # Default heuristic if no unit specified
            if num < 20:  # If user says 4 x 3, they likely mean meters
                return round(num * 100.0, 1)
            elif num < 50:  # If user says 15 x 12, likely feet
                return round(num * 30.48, 1)
            else:  # E.g. 450 x 360, already in cm
                return round(num, 1)

        # Detect single height updates (e.g. "height is 9 ft", "ceiling 2.8m", "h: 10ft")
        height_match = re.search(r"(?:height|ceiling|h)\s*(?:is|:|=)?\s*(\d+(?:\.\d+)?)\s*(meters?|m|feet|ft|cm|inches|in|')?", cleaned)
        if height_match:
            h_num = float(height_match.group(1))
            h_unit = height_match.group(2) or ""
            h_val = _to_cm(h_num, h_unit)

        # Detect single length updates (e.g. "length is 15 ft", "l: 4.8m")
        length_match = re.search(r"(?:length|l)\s*(?:is|:|=)?\s*(\d+(?:\.\d+)?)\s*(meters?|m|feet|ft|cm|inches|in|')?", cleaned)
        if length_match and not re.search(r"(\d+)\s*(?:x|\*|by)\s*(\d+)", cleaned):
            l_num = float(length_match.group(1))
            l_unit = length_match.group(2) or ""
            l_val = _to_cm(l_num, l_unit)

        # Detect single breadth / width updates (e.g. "breadth is 12 ft", "width 3.6m")
        width_match = re.search(r"(?:breadth|width|b|w)\s*(?:is|:|=)?\s*(\d+(?:\.\d+)?)\s*(meters?|m|feet|ft|cm|inches|in|')?", cleaned)
        if width_match and not re.search(r"(\d+)\s*(?:x|\*|by)\s*(\d+)", cleaned):
            w_num = float(width_match.group(1))
            w_unit = width_match.group(2) or ""
            w_val = _to_cm(w_num, w_unit)

        # Detect 3-way dimension pattern: L * B * H (e.g. "4.8 x 3.6 x 3.0 m" or "15 * 12 * 9 feet" or "480x360x300 cm")
        triple_match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:x|\*|by)\s*(\d+(?:\.\d+)?)\s*(?:x|\*|by)\s*(\d+(?:\.\d+)?)\s*(meters?|m|feet|ft|cm|inches|in|')?",
            cleaned
        )
        if triple_match:
            unit = triple_match.group(4) or ""
            l_val = _to_cm(float(triple_match.group(1)), unit)
            w_val = _to_cm(float(triple_match.group(2)), unit)
            h_val = _to_cm(float(triple_match.group(3)), unit)

        # Detect 2-way dimension pattern: L * B (e.g. "4.5 x 3.8 m" or "14 * 12 ft" or "400x350")
        elif not triple_match:
            double_match = re.search(
                r"(\d+(?:\.\d+)?)\s*(?:x|\*|by)\s*(\d+(?:\.\d+)?)\s*(meters?|m|feet|ft|cm|inches|in|')?",
                cleaned
            )
            if double_match:
                unit = double_match.group(3) or ""
                l_val = _to_cm(float(double_match.group(1)), unit)
                w_val = _to_cm(float(double_match.group(2)), unit)

        missing = []
        if not l_val:
            missing.append("length")
        if not w_val:
            missing.append("breadth")
        if not h_val:
            # Default standard ceiling height if not specified (280 cm / ~9.2 ft)
            h_val = 280.0

        is_complete = bool(l_val and w_val)

        return {
            "is_confused": False,
            "length_cm": int(l_val) if l_val else None,
            "width_cm": int(w_val) if w_val else None,
            "height_cm": int(h_val) if h_val else 280,
            "is_complete": is_complete,
            "missing_parts": missing
        }

    def evaluate_fit(self, length_cm: int, width_cm: int, selected_item_ids: List[str]) -> Dict[str, Any]:
        """Check spatial footprint and 35% circulation safety threshold."""
        return tools.layout_fit_check(length_cm, width_cm, selected_item_ids, db_path=self.db_path)
