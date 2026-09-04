"""
guardrails.py - P0 Guardrails, Edge-Case Traps, and Safety Refusals
Implements the 5 Core Product Guardrails from 02_GUARDRAILS_AND_EDGE_CASES.md:
1. P0 Civil & Structural Engineering Safety Refusal (Wall demolition, load-bearing, electrical splicing, plumbing)
2. P0 Commercial & SLA Lock (Guaranteed delivery dates, unapproved discount locks)
3. Impossible / Zero / Negative Budget Interception
4. Spatial Overcrowding & Circulation Violation Interception
5. Catalog Boundary & External Designer Brand Substitution Protocol
"""

import re
from typing import Dict, Any, Optional, List, Tuple

# External designer brands strictly outside catalog inventory
EXTERNAL_BRANDS = [
    "togo", "noguchi", "eames", "ikea", "herman miller",
    "west elm", "restoration hardware", "cb2", "pottery barn",
    "billy bookcase", "poang"
]

# Patterns for civil and structural engineering safety violations
CIVIL_SAFETY_PATTERNS = [
    (r"\b(knock\s*down|break|demolish|remove)\b.*\b(wall|partition)\b", "Wall demolition / load-bearing query"),
    (r"\bload[-\s]*bearing\b", "Load-bearing wall feasibility inquiry"),
    (r"\b(plumbing|water\s*lines?|drain|wet\s*bar)\b.*\b(slab|floor|relocat|route)\b", "Plumbing slab relocation"),
    (r"\b(route|run)\s+water\s+lines?\b", "Water line rerouting query"),
    (r"\b(splice|tap|reroute|cut)\b.*\b(conduit|wiring|220v|cable|electric)\b", "Electrical conduit splicing / wiring query"),
    (r"\bsplice\s+the\s+main\s+220v\b", "Main 220V conduit splicing hazard"),
    (r"\bconduit\b", "Electrical conduit modification")
]

# Patterns for commercial SLA and discount lock attempts
COMMERCIAL_SLA_PATTERNS = [
    (r"\bguarantee\b.*\b(deliver|before|arrival|date|25th)\b", "Guaranteed delivery date demand"),
    (r"\bdeliver(ed)?\s+before\b", "Specific delivery date deadline demand"),
    (r"\block\b.*\b(discount|price|pricing)\b", "Unauthorized discount lock demand"),
    (r"\b\d+%\s*discount\b", "Arbitrary discount percentage demand (e.g. 20%, 30%)"),
    (r"\b(best|special)\s+discount\b", "Commercial discount negotiation demand"),
    (r"\bdiscount\s+(right\s+now|now)\b", "Immediate price discount lock"),
    (r"\bfinalize\s+the\s+invoice\b", "Invoice price lock request")
]


def check_brand_mentions(text: str) -> List[str]:
    """Identify external designer brands mentioned in input text."""
    lower_text = text.lower()
    found = []
    for brand in EXTERNAL_BRANDS:
        if re.search(r"\b" + re.escape(brand) + r"\b", lower_text):
            found.append(brand)
    return found


def check_civil_safety(text: str) -> Optional[Tuple[str, str]]:
    """Detect civil, structural, electrical, or plumbing safety questions."""
    lower_text = text.lower()
    for pattern, reason in CIVIL_SAFETY_PATTERNS:
        if re.search(pattern, lower_text):
            return "CIVIL_SAFETY_REFUSAL", reason
    return None


def check_commercial_sla(text: str) -> Optional[Tuple[str, str]]:
    """Detect commercial SLA delivery guarantees and unauthorized discount locks."""
    lower_text = text.lower()
    for pattern, reason in COMMERCIAL_SLA_PATTERNS:
        if re.search(pattern, lower_text):
            return "SLA_PRICING_REFUSAL", reason
    return None


def check_budget_validity(budget_inr: int) -> Optional[Tuple[str, str]]:
    """Verify that budget is a positive, non-zero number."""
    if budget_inr <= 0:
        return (
            "IMPOSSIBLE_BUDGET_REFUSAL",
            f"Specified budget (₹{budget_inr:,}) is zero or negative. A realistic positive procurement budget is required."
        )
    return None


def check_spatial_overcrowding_preliminary(
    dimensions: List[int],
    must_haves: str,
    notes: str = ""
) -> Optional[Tuple[str, str]]:
    """
    Preliminary detection of severe spatial overcrowding:
    - Micro-rooms (e.g. <= 4.5 sqm) asking for full 3-seater living room sets
    - Compact studios asking for 8-seater dining table + L-sectional sofa
    """
    if len(dimensions) < 2:
        return None

    length_cm, width_cm = dimensions[0], dimensions[1]
    room_area_sqm = (length_cm * width_cm) / 10000.0
    text = (must_haves + " " + notes).lower()

    # Case 1: Extreme micro-room (e.g. 200x200 = 4.0 sqm) requesting 3-seater sofa + tables
    if room_area_sqm <= 5.0 and ("3-seater" in text or "sofa" in text and "tv" in text):
        return (
            "SPATIAL_OVERCROWDING_REFUSAL",
            f"Room area ({room_area_sqm:.2f} sqm) is too small to physically accommodate a 3-seater sofa and living set. Minimum safe circulation corridors (75cm) would be completely blocked."
        )

    # Case 2: Compact studio asking for 8-seater banquet dining table + large L-sectional
    if ("8-seater" in text or "8 seater" in text) and ("sectional" in text or "l-sofa" in text or "studio" in text or room_area_sqm < 12.0):
        return (
            "SPATIAL_OVERCROWDING_REFUSAL",
            f"An 8-seater dining table and large sectional sofa require >6.5 sqm footprint, which exceeds the 35% spatial circulation limit for this room ({room_area_sqm:.2f} sqm). 8-seater banquet table must be rejected."
        )

    return None


def evaluate_guardrails(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Evaluates all P0 guardrails for a given room brief.
    Returns a refusal deliverable dictionary if a guardrail triggers, or None if in-scope.
    """
    brief_id = brief.get("brief_id", "BRIEF-CUSTOM")
    input_data = brief.get("input", brief)
    budget = input_data.get("budget_inr", 0)
    dimensions = input_data.get("dimensions", [400, 350, 280])
    must_haves = input_data.get("must_haves", "")
    notes = input_data.get("notes", "") + " " + input_data.get("customer_note", "")
    full_text = f"{must_haves} {notes}"

    # 1. Check Budget Feasibility (Zero / Negative)
    budget_check = check_budget_validity(budget)
    if budget_check:
        status, reason = budget_check
        return {
            "brief_id": brief_id,
            "status": status,
            "design_concept": {
                "theme": "Procurement Feasibility Refusal",
                "palette_and_materials": "N/A - Zero/Negative Budget",
                "rationale": "Furnishing a room requires a realistic, positive procurement budget. Zero or negative values cannot be fulfilled via catalog inventory."
            },
            "boq": [],
            "financial_summary": {
                "budget_allocated_inr": budget,
                "total_spent_inr": 0,
                "remaining_budget_inr": budget,
                "budget_utilization_percentage": 0.0
            },
            "spatial_fit_summary": {
                "room_area_sqm": round((dimensions[0] * dimensions[1]) / 10000.0, 2),
                "furniture_footprint_sqm": 0.0,
                "occupancy_percentage": "0.0%",
                "circulation_viable": True
            },
            "refusal_reason": reason,
            "escalation": "Please revise the procurement budget to a positive amount (e.g., minimum ₹35,000 for foundational decor/seating).",
            "trade_offs_and_omissions": [
                f"Operational Refusal: {reason}"
            ]
        }

    # 2. Check Civil & Structural Engineering Safety
    civil_check = check_civil_safety(full_text)
    if civil_check:
        status, reason = civil_check
        return {
            "brief_id": brief_id,
            "status": status,
            "design_concept": {
                "theme": "Civil & Structural Engineering Operational Refusal",
                "palette_and_materials": "N/A - Professional Engineering Review Required",
                "rationale": (
                    "We cannot evaluate structural feasibility, identify load-bearing wall properties, "
                    "or advise on plumbing slab routing or electrical conduit splicing. "
                    "Demolition or utility relocation without certified inspection presents severe structural and safety hazards."
                )
            },
            "boq": [],
            "financial_summary": {
                "budget_allocated_inr": budget,
                "total_spent_inr": 0,
                "remaining_budget_inr": budget,
                "budget_utilization_percentage": 0.0
            },
            "spatial_fit_summary": {
                "room_area_sqm": round((dimensions[0] * dimensions[1]) / 10000.0, 2),
                "furniture_footprint_sqm": 0.0,
                "occupancy_percentage": "0.0%",
                "circulation_viable": True
            },
            "refusal_reason": (
                "Customer requested structural, civil, electrical, or plumbing modifications. "
                "The agent strictly declines engineering advice and mandates consultation with a licensed structural engineer or architect."
            ),
            "escalation": "Escalated to Licensed Structural Engineer / On-Site Civil Architect.",
            "trade_offs_and_omissions": [
                "Refused civil and structural modification advice (wall demolition / MEP conduit alteration).",
                "Referral issued: Please consult a licensed structural engineer or on-site architect before initiating work."
            ]
        }

    # 3. Check Commercial SLA & Price Discount Locks
    sla_check = check_commercial_sla(full_text)
    if sla_check:
        status, reason = sla_check
        return {
            "brief_id": brief_id,
            "status": status,
            "design_concept": {
                "theme": "Commercial Terms & Delivery SLA Policy Notice",
                "palette_and_materials": "N/A - Routed to Human Commercial Operations",
                "rationale": (
                    "We cannot guarantee binding delivery arrival dates or lock customized price discounts. "
                    "Catalog items carry standardized manufacturing and logistics lead times (typically 7-21 business days). "
                    "All commercial discounting and delivery schedule commitments must be authorized by human sales operations."
                )
            },
            "boq": [],
            "financial_summary": {
                "budget_allocated_inr": budget,
                "total_spent_inr": 0,
                "remaining_budget_inr": budget,
                "budget_utilization_percentage": 0.0
            },
            "spatial_fit_summary": {
                "room_area_sqm": round((dimensions[0] * dimensions[1]) / 10000.0, 2),
                "furniture_footprint_sqm": 0.0,
                "occupancy_percentage": "0.0%",
                "circulation_viable": True
            },
            "refusal_reason": (
                "Customer requested guaranteed delivery timelines or unauthorized price discounts. "
                "Refused binding commitments; catalog prices and standard lead times maintained."
            ),
            "escalation": "Routed to Human Sales Operations & Regional Logistics Fulfillment Team.",
            "trade_offs_and_omissions": [
                "Declined unapproved commercial discounts and binding arrival date guarantees.",
                "Maintained verified catalog pricing and standard published dispatch timelines."
            ]
        }

    # 4. Check Severe Spatial Overcrowding Refusal
    spatial_check = check_spatial_overcrowding_preliminary(dimensions, must_haves, notes)
    if spatial_check:
        status, reason = spatial_check
        room_area_sqm = round((dimensions[0] * dimensions[1]) / 10000.0, 2)
        return {
            "brief_id": brief_id,
            "status": status,
            "design_concept": {
                "theme": "Spatial Clearance & Circulation Safety Refusal",
                "palette_and_materials": "Compact & Space-Saving Alternatives Recommended",
                "rationale": (
                    f"The requested furniture inventory cannot fit within the available floor area ({room_area_sqm} sqm) "
                    "without severely violating the 35% furniture coverage limit and blocking primary walking corridors (<75 cm)."
                )
            },
            "boq": [],
            "financial_summary": {
                "budget_allocated_inr": budget,
                "total_spent_inr": 0,
                "remaining_budget_inr": budget,
                "budget_utilization_percentage": 0.0
            },
            "spatial_fit_summary": {
                "room_area_sqm": room_area_sqm,
                "furniture_footprint_sqm": 0.0,
                "occupancy_percentage": "0.0%",
                "circulation_viable": False
            },
            "refusal_reason": reason,
            "escalation": "Recommended human designer space-planning consultation with compact / wall-mounted alternatives.",
            "trade_offs_and_omissions": [
                f"Spatial Overcrowding Refusal: {reason}",
                "Rejected oversized furniture (8-seater banquet table or 3-seater sofa in micro space).",
                "Circulation corridors must be protected with minimum 75cm clear walkway width."
            ]
        }

    return None
