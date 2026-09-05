"""
agents/budget_agent.py - Budget Specialist Agent
Handles:
1. Natural language budget parsing (ranges, min/max, lakhs/k, no budget/skip)
2. Running cost calculation and overage detection
3. Overage diagnosis (explaining why a selection is over budget)
4. Recommending budget-friendly swaps to bring plans within budget
"""

import os
import re
from typing import Dict, Any, List, Optional, Tuple

import tools

DB_PATH = tools.DB_PATH


class BudgetAgent:
    """Specialist sub-agent for budget interpretation, tracking, and overage optimization."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH

    def parse_budget_input(self, text: str) -> Dict[str, Any]:
        """
        Parses natural language budget expressions into numerical boundaries.
        Returns:
            {
                "is_skipped": bool,
                "raw_text": str,
                "budget_target": Optional[int],
                "budget_min": Optional[int],
                "budget_max": Optional[int],
                "explanation": str
            }
        """
        if not text:
            return {
                "is_skipped": True,
                "raw_text": "",
                "budget_target": None,
                "budget_min": None,
                "budget_max": None,
                "explanation": "No budget provided; plan will be built using standard catalog allowance."
            }

        cleaned = text.strip().lower()

        # Check for skip / don't know / confused
        skip_phrases = [
            "don't know", "dont know", "confused", "no budget", "i don't have a budget",
            "i dont have a budget", "not sure", "skip", "no idea", "any budget"
        ]
        if any(p in cleaned for p in skip_phrases):
            return {
                "is_skipped": True,
                "raw_text": text,
                "budget_target": None,
                "budget_min": None,
                "budget_max": None,
                "explanation": "Budget skipped per client request; standard balanced catalog items will be recommended."
            }

        def _extract_number(val_str: str) -> Optional[int]:
            v = val_str.replace(",", "").replace("₹", "").strip()
            # Handle lakhs (e.g. 2.5L, 2 lakhs, 2 lac)
            lakh_match = re.search(r"(\d+(\.\d+)?)\s*(lakhs?|lac|l)\b", v)
            if lakh_match:
                return int(float(lakh_match.group(1)) * 100000)
            # Handle k / thousands (e.g. 50k, 50 thousand)
            k_match = re.search(r"(\d+(\.\d+)?)\s*(k|thousand)\b", v)
            if k_match:
                return int(float(k_match.group(1)) * 1000)
            # Regular integer
            num_match = re.search(r"\b\d+\b", v)
            if num_match:
                return int(num_match.group(0))
            return None

        # Pattern 1: Between X and Y (e.g. "between 1 lakh and 2 lakhs", "1.5L to 2L", "50000 - 100000")
        between_match = re.search(r"(?:between\s+)?([^\s]+(?:\s+lakhs?)?)\s*(?:to|-|and)\s*([^\s]+(?:\s+lakhs?)?)", cleaned)
        if between_match and ("between" in cleaned or "to" in cleaned or "-" in cleaned):
            n1 = _extract_number(between_match.group(1))
            n2 = _extract_number(between_match.group(2))
            if n1 and n2:
                b_min, b_max = min(n1, n2), max(n1, n2)
                return {
                    "is_skipped": False,
                    "raw_text": text,
                    "budget_target": b_max,
                    "budget_min": b_min,
                    "budget_max": b_max,
                    "explanation": f"Budget range identified: ₹{b_min:,} to ₹{b_max:,}"
                }

        # Pattern 2: More than X / Above X / Greater than X
        more_match = re.search(r"(?:more than|above|greater than|over|at least|minimum)\s*(.*)", cleaned)
        if more_match:
            val = _extract_number(more_match.group(1))
            if val:
                return {
                    "is_skipped": False,
                    "raw_text": text,
                    "budget_target": val * 2,  # Upper target allowance
                    "budget_min": val,
                    "budget_max": None,
                    "explanation": f"Minimum budget baseline: ₹{val:,}"
                }

        # Pattern 3: Less than X / Under X / Below X / Within X
        less_match = re.search(r"(?:less than|under|below|within|maximum|upto|up to)\s*(.*)", cleaned)
        if less_match:
            val = _extract_number(less_match.group(1))
            if val:
                return {
                    "is_skipped": False,
                    "raw_text": text,
                    "budget_target": val,
                    "budget_min": 0,
                    "budget_max": val,
                    "explanation": f"Budget ceiling: ₹{val:,}"
                }

        # Pattern 4: Direct single amount
        val = _extract_number(cleaned)
        if val:
            return {
                "is_skipped": False,
                "raw_text": text,
                "budget_target": val,
                "budget_min": 0,
                "budget_max": val,
                "explanation": f"Target budget allocated: ₹{val:,}"
            }

        # Fallback if no numeric value recognized
        return {
            "is_skipped": True,
            "raw_text": text,
            "budget_target": None,
            "budget_min": None,
            "budget_max": None,
            "explanation": "Could not extract exact budget amount; proceeding with flexible allowance."
        }

    def calculate_cost(self, selected_item_ids: List[str], target_budget: Optional[int] = None) -> Dict[str, Any]:
        """Compute running budget metrics via deterministic calculator tool."""
        effective_budget = target_budget if target_budget is not None and target_budget > 0 else 500000
        return tools.budget_calculator(selected_item_ids, effective_budget, db_path=self.db_path)

    def diagnose_and_recommend_swaps(
        self,
        selected_item_ids: List[str],
        target_budget: int
    ) -> Dict[str, Any]:
        """
        If selections exceed budget, identifies the highest cost drivers,
        explains the specific reason, and recommends budget-friendly swaps.
        """
        calc = self.calculate_cost(selected_item_ids, target_budget)
        if not calc["is_over_budget"]:
            return {
                "is_over_budget": False,
                "overage_amount": 0,
                "recommendation": "Current selections fit comfortably within your allocated budget.",
                "swapped_item_ids": selected_item_ids
            }

        overage = calc["overage_amount"]
        # Find highest cost items
        breakdown = sorted(calc["breakdown"], key=lambda x: (x["price"] or 0), reverse=True)

        swaps = []
        new_ids = list(selected_item_ids)

        for item in breakdown:
            if item["price"] and item["price"] > 40000:
                cat = item["category"]
                # Search for lower-priced alternative in the same category
                cheaper_items = tools.catalog_search(category=cat, max_price=item["price"] - 15000, in_stock_only=True, db_path=self.db_path)
                if cheaper_items:
                    best_alt = cheaper_items[0]
                    diff = item["price"] - (best_alt["price_inr"] or 0)
                    swaps.append({
                        "original_id": item["item_id"],
                        "original_name": item["name"],
                        "original_price": item["price"],
                        "replacement_id": best_alt["item_id"],
                        "replacement_name": best_alt["name"],
                        "replacement_price": best_alt["price_inr"],
                        "savings": diff
                    })
                    # Perform swap
                    if item["item_id"] in new_ids:
                        new_ids.remove(item["item_id"])
                        new_ids.append(best_alt["item_id"])
                    break

        new_calc = self.calculate_cost(new_ids, target_budget)

        reasons = [
            f"Your current selection total of ₹{calc['total_spent']:,} exceeds your budget limit of ₹{target_budget:,} by ₹{overage:,}."
        ]
        if swaps:
            s = swaps[0]
            reasons.append(
                f"Recommendation: Swap {s['original_name']} (₹{s['original_price']:,}) with {s['replacement_name']} (₹{s['replacement_price']:,}) "
                f"to save ₹{s['savings']:,} and bring your total down to ₹{new_calc['total_spent']:,}."
            )
        else:
            reasons.append("Recommendation: Defer secondary accent lighting or decor pieces to Phase 2 to meet your budget.")

        return {
            "is_over_budget": True,
            "overage_amount": overage,
            "explanation": " ".join(reasons),
            "swaps": swaps,
            "swapped_item_ids": new_ids,
            "revised_spent": new_calc["total_spent"]
        }
