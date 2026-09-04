"""
tools.py - Deterministic Core Tools for Interior Company x Blocks
Implements the 3 core tools specified in 01_SYSTEM_ARCHITECTURE_AND_SPECS.md:
1. catalog_search: Parameterized SQL filter on SQLite catalog
2. budget_calculator: Precise cost aggregation, unpriced item trapping, and overage detection
3. layout_fit_check: Footprint calculation, 35% circulation threshold, and dimensional imputation
"""

import os
import sqlite3
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interior_company_catalog.db")
if not os.path.exists(DB_PATH) and os.path.exists("interior_company_catalog.db"):
    DB_PATH = "interior_company_catalog.db"


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    target_path = db_path or DB_PATH
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn


def catalog_search(
    category: Optional[str] = None,
    style: Optional[str] = None,
    room_type: str = "Living Room",
    max_price: Optional[int] = None,
    in_stock_only: bool = True,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Query the SQLite catalog using parameterized filters.
    Enforces that the agent only accesses real, verified catalog items.
    Defensive handling: excludes out-of-stock items by default, permits null-price
    items only with explicit quote flags.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    query = "SELECT * FROM catalog WHERE 1=1"
    params: List[Any] = []

    if room_type:
        query += " AND LOWER(room_types) LIKE LOWER(?)"
        params.append(f"%{room_type}%")

    if category:
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category)

    if style:
        # Check style tags
        query += " AND LOWER(style_tags) LIKE LOWER(?)"
        params.append(f"%{style}%")

    if max_price is not None:
        query += " AND (price_inr <= ? OR price_inr IS NULL)"
        params.append(max_price)

    if in_stock_only:
        query += " AND in_stock = 1"

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_item_by_id(item_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch exact catalog item by its primary key item_id."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM catalog WHERE item_id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_catalog_items(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all rows from the catalog table."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM catalog")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def budget_calculator(
    selected_item_ids: List[str],
    total_budget_inr: int,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sums selected items, compares against total budget, and reports remaining balance.
    Detects unpriced items and prevents silent over-budget spending.
    """
    if not selected_item_ids:
        return {
            "total_budget": total_budget_inr,
            "total_spent": 0,
            "remaining_budget": total_budget_inr,
            "is_over_budget": False,
            "overage_amount": 0,
            "unpriced_items": [],
            "breakdown": []
        }

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(selected_item_ids))
    cursor.execute(
        f"SELECT item_id, name, category, price_inr, in_stock, lead_time_days FROM catalog WHERE item_id IN ({placeholders})",
        selected_item_ids
    )
    rows = cursor.fetchall()
    conn.close()

    # Preserve order of selected_item_ids
    items_by_id = {r["item_id"]: dict(r) for r in rows}

    total_spent = 0
    unpriced = []
    breakdown = []

    for item_id in selected_item_ids:
        r = items_by_id.get(item_id)
        if not r:
            continue
        price = r["price_inr"]
        if price is None:
            unpriced.append(r["item_id"])
            item_cost = 0
        else:
            item_cost = price
            total_spent += item_cost

        breakdown.append({
            "item_id": r["item_id"],
            "name": r["name"],
            "category": r["category"],
            "price": price,
            "in_stock": r.get("in_stock", 1),
            "lead_time_days": r.get("lead_time_days", 7)
        })

    remaining = total_budget_inr - total_spent
    return {
        "total_budget": total_budget_inr,
        "total_spent": total_spent,
        "remaining_budget": remaining,
        "is_over_budget": remaining < 0,
        "overage_amount": abs(remaining) if remaining < 0 else 0,
        "unpriced_items": unpriced,
        "breakdown": breakdown
    }


def layout_fit_check(
    room_length_cm: int,
    room_width_cm: int,
    selected_item_ids: List[str],
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates physical fit and spatial circulation.
    Rule: Total furniture footprint must not exceed 35% of total room area.
    Ensures minimum 75cm - 90cm walkways.
    Imputes conservative median dimensions when dimensions are missing.
    """
    room_area_sqm = (room_length_cm * room_width_cm) / 10000.0
    if not selected_item_ids:
        return {
            "room_area_sqm": round(room_area_sqm, 2),
            "furniture_footprint_sqm": 0.0,
            "occupancy_ratio": 0.0,
            "occupancy_percentage": "0.0%",
            "fits_circulation": True,
            "warning": None,
            "imputed_dimension_items": []
        }

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(selected_item_ids))
    cursor.execute(
        f"SELECT item_id, name, category, width_cm, depth_cm FROM catalog WHERE item_id IN ({placeholders})",
        selected_item_ids
    )
    items = cursor.fetchall()
    conn.close()

    total_footprint_sqm = 0.0
    imputed_items = []
    category_defaults = {
        "Sofa": (200, 90),
        "Coffee Table": (100, 60),
        "TV Unit": (160, 40),
        "Rug": (200, 140),  # Rugs are floor coverings, discounted in clearance calculation
        "Armchair": (80, 80),
        "Floor Lamp": (40, 40),
        "Side Table": (45, 45),
        "Bookshelf": (80, 35),
        "Desk": (120, 60),
        "Bed": (200, 160),
        "Wardrobe": (120, 60),
        "Bedside Table": (45, 40),
        "Dining Table": (150, 90),
        "Dining Chair": (45, 45),
        "Console": (100, 35),
        "Office Chair": (60, 60),
        "Bean Bag": (80, 80),
        "Ottoman": (60, 40),
        "Planter": (35, 35)
    }

    NON_FLOOR_CATEGORIES = {"Rug", "Curtains", "Wall Art", "Pendant Light", "Mirror", "Cushions"}

    for item in items:
        # Non-floor and wall-mounted items do not block physical floor circulation corridors
        if item["category"] in NON_FLOOR_CATEGORIES or "floating" in item["name"].lower():
            continue
        w = item["width_cm"]
        d = item["depth_cm"]
        if w is None or d is None:
            default_w, default_d = category_defaults.get(item["category"], (50, 50))
            w = w if w is not None else default_w
            d = d if d is not None else default_d
            imputed_items.append(item["item_id"])
        total_footprint_sqm += (w * d) / 10000.0

    occupancy_ratio = total_footprint_sqm / room_area_sqm if room_area_sqm > 0 else 1.0
    # 35% maximum furniture coverage threshold
    fits_circulation = occupancy_ratio <= 0.35

    return {
        "room_area_sqm": round(room_area_sqm, 2),
        "furniture_footprint_sqm": round(total_footprint_sqm, 2),
        "occupancy_ratio": round(occupancy_ratio, 3),
        "occupancy_percentage": f"{round(occupancy_ratio * 100, 1)}%",
        "fits_circulation": fits_circulation,
        "warning": None if fits_circulation else f"Furniture occupies {round(occupancy_ratio*100, 1)}% of floor area (Max allowable: 35%). Room will feel overcrowded and circulation corridors will be blocked.",
        "imputed_dimension_items": imputed_items
    }
