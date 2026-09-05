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
        Supports:
        - 3 numbers in one go: '200 290 310', '200 x 210 x 310', '15 * 12 * 9 feet', '4.5 3.5 2.8'
        - Labeled inputs: 'length is 200, breadth is 210 and height is 300', 'l=200 b=210 h=300'
        - 2 numbers in one go: '200 210' -> sets length & breadth, prompts for height
        - Single number follow-up: '200' or '310' -> sets missing height
        - Mixed units and automatic heuristics
        """
        if not text:
            missing = [p for p, v in [("length", current_l), ("breadth", current_w), ("height", current_h)] if not v]
            return {
                "is_confused": True,
                "length_cm": current_l,
                "width_cm": current_w,
                "height_cm": current_h,
                "is_complete": bool(current_l and current_w and current_h),
                "missing_parts": missing
            }

        cleaned = text.strip().lower()

        # Check for confused / refusal keywords
        confused_phrases = ["don't know", "dont know", "confused", "not sure", "no idea", "can't measure", "cant measure"]
        if any(p in cleaned for p in confused_phrases):
            # If length and width are already known, and user doesn't know height, default height to 280 cm!
            if current_l and current_w and not current_h:
                return {
                    "is_confused": False,
                    "length_cm": int(round(current_l)),
                    "width_cm": int(round(current_w)),
                    "height_cm": 280,
                    "is_complete": True,
                    "missing_parts": []
                }
            return {
                "is_confused": True,
                "length_cm": current_l,
                "width_cm": current_w,
                "height_cm": current_h,
                "is_complete": False,
                "missing_parts": ["length", "breadth", "height"]
            }

        # If user says "standard height", "default", etc. when only height is missing:
        if current_l and current_w and not current_h:
            if any(p in cleaned for p in ["standard", "default", "normal", "average", "regular"]):
                return {
                    "is_confused": False,
                    "length_cm": int(round(current_l)),
                    "width_cm": int(round(current_w)),
                    "height_cm": 280,
                    "is_complete": True,
                    "missing_parts": []
                }

        l_val = current_l
        w_val = current_w
        h_val = current_h

        def infer_group_unit(numbers: List[float], explicit_unit: str = "") -> str:
            if explicit_unit:
                return explicit_unit
            if any(n > 40 for n in numbers):
                return "cm"
            if any(8 <= n <= 40 for n in numbers):
                return "ft"
            return "m"

        def to_cm(num: float, unit_str: str) -> float:
            u = unit_str.strip().lower() if unit_str else "cm"
            if "m" in u and "cm" not in u:
                return round(num * 100.0, 1)
            elif "ft" in u or "feet" in u or "foot" in u or "'" in u:
                return round(num * 30.48, 1)
            elif "in" in u or "inch" in u or '"' in u:
                return round(num * 2.54, 1)
            elif "cm" in u:
                return round(num, 1)
            return round(num, 1)

        # Check for global unit keyword anywhere in string
        global_unit = ""
        if re.search(r"\b(meters?|mtrs?)\b", cleaned):
            global_unit = "m"
        elif re.search(r"\b(feet|foot|ft|')\b", cleaned):
            global_unit = "ft"
        elif re.search(r"\b(inches|inch|\")\b", cleaned):
            global_unit = "in"
        elif re.search(r"\b(cm|cms|centimeters?)\b", cleaned):
            global_unit = "cm"

        unit_pattern = r"(meters?|mtrs?|m|feet|foot|ft|cm|cms|centimeters?|inches|inch|\"|')"

        # 1. Check for labeled dimensions (label-first and number-first)
        # Length
        len_match = re.search(rf"\b(?:length|len|long|l)\b\s*(?:is|of|=|:)?\s*(\d+(?:\.\d+)?)\s*{unit_pattern}?", cleaned)
        if not len_match:
            len_match = re.search(rf"(\d+(?:\.\d+)?)\s*{unit_pattern}?\s*(?:is|in)?\s*\b(?:length|len|long|l)\b", cleaned)

        # Width / Breadth
        wid_match = re.search(rf"\b(?:breadth|width|wide|b|w)\b\s*(?:is|of|=|:)?\s*(\d+(?:\.\d+)?)\s*{unit_pattern}?", cleaned)
        if not wid_match:
            wid_match = re.search(rf"(\d+(?:\.\d+)?)\s*{unit_pattern}?\s*(?:is|in)?\s*\b(?:breadth|width|wide|b|w)\b", cleaned)

        # Height
        hgt_match = re.search(rf"\b(?:height|ceiling|tall|h)\b\s*(?:is|of|=|:)?\s*(\d+(?:\.\d+)?)\s*{unit_pattern}?", cleaned)
        if not hgt_match:
            hgt_match = re.search(rf"(\d+(?:\.\d+)?)\s*{unit_pattern}?\s*(?:is|in)?\s*\b(?:height|ceiling|tall|h)\b", cleaned)

        unlabeled_text = cleaned

        if len_match:
            u = len_match.group(2) or global_unit
            l_val = to_cm(float(len_match.group(1)), u or infer_group_unit([float(len_match.group(1))]))
            unlabeled_text = unlabeled_text.replace(len_match.group(0), " ")

        if wid_match:
            u = wid_match.group(2) or global_unit
            w_val = to_cm(float(wid_match.group(1)), u or infer_group_unit([float(wid_match.group(1))]))
            unlabeled_text = unlabeled_text.replace(wid_match.group(0), " ")

        if hgt_match:
            u = hgt_match.group(2) or global_unit
            h_val = to_cm(float(hgt_match.group(1)), u or infer_group_unit([float(hgt_match.group(1))]))
            unlabeled_text = unlabeled_text.replace(hgt_match.group(0), " ")

        # 2. If not all 3 were matched by labels, extract numeric tokens from unlabeled text
        if not (l_val and w_val and h_val):
            num_regex = rf"(\d+(?:\.\d+)?)\s*{unit_pattern}?"
            tokens = []
            for m in re.finditer(num_regex, unlabeled_text):
                val = float(m.group(1))
                unit = m.group(2) or global_unit
                tokens.append((val, unit))

            nums = [t[0] for t in tokens]
            has_any_explicit_unit = any(bool(t[1]) for t in tokens) or bool(global_unit)
            group_unit = infer_group_unit(nums, global_unit) if not has_any_explicit_unit else global_unit

            if len(tokens) >= 3:
                # 3 numbers in one go: 1st = length, 2nd = breadth, 3rd = height!
                if not (l_val or w_val or h_val):
                    l_val = to_cm(tokens[0][0], tokens[0][1] or group_unit)
                    w_val = to_cm(tokens[1][0], tokens[1][1] or group_unit)
                    h_val = to_cm(tokens[2][0], tokens[2][1] or group_unit)
                else:
                    # Fill missing slots in order
                    for val, unit in tokens:
                        v_cm = to_cm(val, unit or group_unit)
                        if not l_val:
                            l_val = v_cm
                        elif not w_val:
                            w_val = v_cm
                        elif not h_val:
                            h_val = v_cm
            elif len(tokens) == 2:
                t0_cm = to_cm(tokens[0][0], tokens[0][1] or group_unit)
                t1_cm = to_cm(tokens[1][0], tokens[1][1] or group_unit)
                # Assign based on what is already known
                if l_val and not w_val and not h_val:
                    w_val = t0_cm
                    h_val = t1_cm
                elif h_val and not l_val and not w_val:
                    l_val = t0_cm
                    w_val = t1_cm
                elif w_val and not l_val and not h_val:
                    l_val = t0_cm
                    h_val = t1_cm
                elif not l_val and not w_val:
                    l_val = t0_cm
                    w_val = t1_cm
            elif len(tokens) == 1:
                val, unit = tokens[0]
                val_cm = to_cm(val, unit or group_unit)
                # If length and breadth are already known, this single number is height!
                if (current_l or l_val) and (current_w or w_val) and not h_val:
                    h_val = val_cm
                elif not l_val:
                    l_val = val_cm
                elif not w_val:
                    w_val = val_cm
                elif not h_val:
                    h_val = val_cm

        missing = []
        if not l_val:
            missing.append("length")
        if not w_val:
            missing.append("breadth")
        if not h_val:
            missing.append("height")

        is_complete = bool(l_val and w_val and h_val)

        return {
            "is_confused": False,
            "length_cm": int(round(l_val)) if l_val else None,
            "width_cm": int(round(w_val)) if w_val else None,
            "height_cm": int(round(h_val)) if h_val else None,
            "is_complete": is_complete,
            "missing_parts": missing
        }

    def evaluate_fit(self, length_cm: int, width_cm: int, selected_item_ids: List[str]) -> Dict[str, Any]:
        """Check spatial footprint and 35% circulation safety threshold."""
        return tools.layout_fit_check(length_cm, width_cm, selected_item_ids, db_path=self.db_path)
