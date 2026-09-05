"""
agents/catalog_agent.py - Catalog Specialist Agent
Handles:
1. Real-time catalog queries on interior_company_catalog.db
2. Style verification against DB styles and suggesting 2-4 alternative styles if unsupported
3. Must-haves suggestion by room type and missing item detection ("Currently we don't have [item] from the must-haves")
4. External brand / item substitutions with in-catalog equivalents
"""

import os
import re
import sqlite3
from typing import Dict, Any, List, Optional, Tuple

import tools

DB_PATH = tools.DB_PATH

# Standard verified styles present across the catalog
CORE_DB_STYLES = [
    "Scandinavian", "Mid-Century", "Minimalist", "Contemporary",
    "Bohemian", "Industrial", "Traditional", "Coastal"
]

# Standard must-haves per room type in catalog
ROOM_MUST_HAVES = {
    "Living Room": ["Sofa", "Coffee Table", "TV Unit", "Rug", "Floor Lamp"],
    "Bedroom": ["Bed", "Wardrobe", "Bedside Table", "Curtains"],
    "Dining": ["Dining Table", "Dining Chair", "Pendant Light", "Console"],
    "Study": ["Desk", "Office Chair", "Bookshelf", "Task Light"],
    "Kids": ["Bed", "Desk", "Bookshelf", "Bean Bag"]
}

# Known external brands / unlisted items and their catalog substitutions
BRAND_SUBSTITUTIONS = {
    "togo": ("Togo Sofa", "SOF-001", "Nordby 3-Seater Fabric Sofa"),
    "noguchi": ("Noguchi Coffee Table", "CFT-001", "Oslo Oak Coffee Table"),
    "eames": ("Eames Lounger", "ACH-001", "Eames-style Lounge Chair"),
    "ikea": ("IKEA Furnishings", "BKS-001", "Ladder Bookshelf & Wishbone Chair"),
    "billy": ("IKEA Billy Bookcase", "BKS-001", "Ladder Bookshelf"),
    "poang": ("IKEA Poang Chair", "ACH-002", "Wishbone Accent Chair"),
    "herman miller": ("Herman Miller Chair", "CHR-001", "Ergonomic Mesh Chair"),
    "recliner": ("Recliner Chair", "ACH-001", "Mid-Century Lounge Armchair"),
    "chandelier": ("Chandelier", "PND-002", "Cluster Glass Pendant Light"),
    "water bed": ("Water Bed", "BED-001", "Hygge Upholstered Queen Bed"),
    "bunk bed": ("Bunk Bed", "BED-001", "Modular Storage Bed"),
    "bar counter": ("Bar Counter", "CON-001", "Entry Server Console")
}


class CatalogAgent:
    """Specialist sub-agent for all product catalog, style, and inventory operations."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH

    def get_all_db_styles(self) -> List[str]:
        """Fetch distinct styles present in catalog style_tags."""
        conn = tools.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT style_tags FROM catalog WHERE style_tags IS NOT NULL")
        rows = cursor.fetchall()
        conn.close()

        styles_set = set(CORE_DB_STYLES)
        for r in rows:
            for s in r[0].split(","):
                clean = s.strip()
                if clean:
                    styles_set.add(clean)
        return sorted(list(styles_set))

    def validate_style(self, user_style_input: str) -> Tuple[bool, Optional[str], List[str]]:
        """
        Validates user-requested style against database styles.
        Returns:
            (is_valid, matched_style_name, suggested_db_styles)
        """
        if not user_style_input:
            return False, None, CORE_DB_STYLES[:3]

        lower_input = user_style_input.strip().lower()
        all_styles = self.get_all_db_styles()

        # Exact or substring match
        for s in all_styles:
            if s.lower() == lower_input or s.lower() in lower_input or lower_input in s.lower():
                return True, s, []

        # Unsupported style: pick 3 representative DB styles as alternatives
        suggested = ["Scandinavian", "Mid-Century", "Contemporary", "Bohemian"]
        return False, None, suggested

    def get_room_must_haves_suggestions(self, room_type: str) -> List[str]:
        """Return typical verified catalog categories for a room type."""
        norm_room = "Living Room"
        for k in ROOM_MUST_HAVES:
            if k.lower() in (room_type or "").lower():
                norm_room = k
                break
        return ROOM_MUST_HAVES.get(norm_room, ROOM_MUST_HAVES["Living Room"])

    def check_must_have_availability(self, item_text: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Checks whether a requested must-have item exists in the DB.
        If missing/unsupported, returns (False, missing_item_name, catalog_recommendation).
        """
        lower = item_text.strip().lower()

        # Check for known external brands or unlisted items
        for key, (label, sub_id, sub_name) in BRAND_SUBSTITUTIONS.items():
            if key in lower:
                rec_item = tools.get_item_by_id(sub_id, db_path=self.db_path)
                return False, label, rec_item or {"item_id": sub_id, "name": sub_name}

        # Check if requested category matches catalog
        categories = self.get_all_categories()
        category_matched = any(c.lower() in lower or lower in c.lower() for c in categories)

        if not category_matched and len(lower) > 3:
            # Item not found in DB categories or brands
            # Suggest a foundational recommendation
            fallback = tools.get_item_by_id("SOF-001", db_path=self.db_path)
            return False, item_text, fallback

        return True, None, None

    def get_all_categories(self) -> List[str]:
        """Return list of distinct categories in the catalog."""
        conn = tools.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM catalog")
        cats = [r[0] for r in cursor.fetchall() if r[0]]
        conn.close()
        return cats

    def search_items(
        self,
        category: Optional[str] = None,
        style: Optional[str] = None,
        room_type: str = "Living Room",
        max_price: Optional[int] = None,
        in_stock_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Query catalog with parameterized filters."""
        return tools.catalog_search(
            category=category,
            style=style,
            room_type=room_type,
            max_price=max_price,
            in_stock_only=in_stock_only,
            db_path=self.db_path
        )
