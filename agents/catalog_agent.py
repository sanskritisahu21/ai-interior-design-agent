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
        Supports case-insensitivity, hyphen-insensitivity (e.g. 'midcentury' -> 'Mid-Century'),
        common abbreviations ('scandi', 'boho', 'mcm'), and token-level matching.
        Returns:
            (is_valid, matched_style_name, suggested_db_styles)
        """
        if not user_style_input:
            return False, None, CORE_DB_STYLES[:3]

        raw = user_style_input.strip()
        lower_input = raw.lower()
        cleaned_input = re.sub(r"\b(style|look|aesthetic|vibe|theme|design|interior|please)\b", "", lower_input).strip()

        def norm(text: str) -> str:
            return re.sub(r"[^a-z0-9]", "", (text or "").lower())

        norm_input = norm(cleaned_input) or norm(lower_input)

        # 1. Known popular style aliases and abbreviations
        aliases = {
            "midcentury": "Mid-Century",
            "midcenturymodern": "Mid-Century",
            "mcm": "Mid-Century",
            "scandi": "Scandinavian",
            "scandinavian": "Scandinavian",
            "minimal": "Minimalist",
            "minimalist": "Minimalist",
            "minimalism": "Minimalist",
            "boho": "Bohemian",
            "bohemian": "Bohemian",
            "contemporary": "Contemporary",
            "modern": "Contemporary",
            "industrial": "Industrial",
            "traditional": "Traditional",
            "classic": "Traditional",
            "coastal": "Coastal",
            "beach": "Coastal",
            "japandi": "Minimalist",
        }

        # Check direct alias dictionary
        if norm_input in aliases:
            return True, aliases[norm_input], []

        for alias_key, target_style in aliases.items():
            if alias_key in norm_input or norm_input in alias_key:
                return True, target_style, []

        all_styles = self.get_all_db_styles()

        # 2. Check normalized exact or substring match against all DB styles
        for s in all_styles:
            ns = norm(s)
            if ns and (ns == norm_input or ns in norm_input or norm_input in ns):
                return True, s, []

        # 3. Check token-level match (e.g. 'mid century' tokens ['mid', 'century'])
        input_tokens = [w for w in re.split(r"[^a-z0-9]+", lower_input) if len(w) > 2]
        for s in all_styles:
            s_tokens = [w for w in re.split(r"[^a-z0-9]+", s.lower()) if len(w) > 2]
            if any(t in s_tokens for t in input_tokens):
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

    def check_must_haves_coverage(
        self,
        user_text: str,
        boq_items: List[Dict[str, Any]],
        room_type: str = "Living Room"
    ) -> Dict[str, Any]:
        """
        Parses user's requested must-haves and checks which items are unavailable in the DB/plan.
        Returns a dict:
          {
            "has_unavailable": bool,
            "unavailable_items": List[str],
            "available_items": List[str],
            "brand_substitutions": List[Tuple[str, str]]
          }
        """
        lower = user_text.strip().lower()

        generic_tokens = ["all", "all of these", "everything", "standard", "any", "don't know", "dont know", "confused"]
        if any(lower == g or lower.startswith(g + " ") for g in generic_tokens):
            avail_cats = []
            for item in boq_items:
                c = item.get("category")
                if c and c not in avail_cats:
                    avail_cats.append(c)
            return {
                "has_unavailable": False,
                "unavailable_items": [],
                "available_items": avail_cats,
                "brand_substitutions": []
            }

        brand_subs = []
        for key, (label, sub_id, sub_name) in BRAND_SUBSTITUTIONS.items():
            if key in lower:
                brand_subs.append((label, sub_name))

        raw_tokens = re.split(r'[,;\n]|\band\b|\b\+\b|\b&\b', user_text, flags=re.IGNORECASE)
        candidates = []
        for t in raw_tokens:
            clean = re.sub(
                r'^(i want|i need|please add|give me|we want|looking for|also|with|a|an|the)\s+',
                '',
                t.strip(),
                flags=re.IGNORECASE
            ).strip()
            if len(clean) >= 2 and clean.lower() not in generic_tokens:
                candidates.append(clean)

        boq_cats = [item.get("category", "").lower() for item in boq_items]
        boq_names = [item.get("name", "").lower() for item in boq_items]

        synonyms = {
            "tv": "tv unit",
            "television": "tv unit",
            "tv stand": "tv unit",
            "media console": "tv unit",
            "tv console": "tv unit",
            "couch": "sofa",
            "couches": "sofa",
            "sofas": "sofa",
            "center table": "coffee table",
            "tea table": "coffee table",
            "standing lamp": "floor lamp",
            "reading lamp": "table lamp",
            "lamp": "floor lamp",
            "lamps": "floor lamp",
            "light": "floor lamp",
            "lights": "floor lamp",
            "lighting": "floor lamp",
            "closet": "wardrobe",
            "almirah": "wardrobe",
            "cupboard": "wardrobe",
            "plant": "planter",
            "plants": "planter",
            "planter": "planter",
            "planters": "planter",
            "greenery": "planter",
            "pot": "planter",
            "pots": "planter",
            "curtain": "curtains",
            "curtains": "curtains",
            "drapes": "curtains",
            "rugs": "rug",
            "arm chair": "armchair",
            "arm chairs": "armchair",
            "accent chair": "armchair",
            "chairs": "dining chair" if "dining" in room_type.lower() else "armchair"
        }

        unavailable = []
        for cand in candidates:
            cand_low = cand.lower()
            mapped = synonyms.get(cand_low, cand_low)
            matched = False
            for cat in boq_cats:
                if mapped in cat or cat in mapped or cand_low in cat:
                    matched = True
                    break
            if not matched:
                for name in boq_names:
                    if mapped in name or name in mapped or cand_low in name:
                        matched = True
                        break
            if not matched:
                # Check if item exists in catalog for room
                # If cand is in brand subs or known unsupported (like soft lighting, chandelier, jacuzzi), verify
                cat_probe = self.find_catalog_item_for_room(cand, room_type=room_type)
                if not cat_probe:
                    unavailable.append(cand)

        avail_cats = []
        for item in boq_items:
            c = item.get("category")
            if c and c not in avail_cats:
                avail_cats.append(c)

        return {
            "has_unavailable": len(unavailable) > 0,
            "unavailable_items": unavailable,
            "available_items": avail_cats,
            "brand_substitutions": brand_subs
        }

    def get_all_categories(self) -> List[str]:
        """Return list of distinct categories in the catalog."""
        conn = tools.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM catalog")
        cats = [r[0] for r in cursor.fetchall() if r[0]]
        conn.close()
        return cats

    def _normalize_room_type(self, room_type: str) -> str:
        """Normalizes room type name for matching DB room_types values."""
        r_low = (room_type or "").lower()
        if "living" in r_low or "hall" in r_low or "drawing" in r_low:
            return "Living Room"
        elif "bed" in r_low:
            return "Bedroom"
        elif "dining" in r_low:
            return "Dining"
        elif "study" in r_low or "office" in r_low or "wfh" in r_low:
            return "Study"
        elif "kid" in r_low or "child" in r_low:
            return "Kids"
        return room_type or "Living Room"

    def get_categories_for_room(self, room_type: str = "Living Room") -> List[str]:
        """Return distinct categories available in catalog for room_type."""
        norm_room = self._normalize_room_type(room_type)
        conn = tools.get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT category FROM catalog WHERE LOWER(room_types) LIKE LOWER(?)",
            (f"%{norm_room}%",)
        )
        cats = sorted([r[0] for r in cursor.fetchall() if r[0]])
        conn.close()
        return cats

    def find_catalog_item_for_room(
        self,
        keyword: str,
        room_type: str = "Living Room",
        style: str = "Scandinavian"
    ) -> Optional[Dict[str, Any]]:
        """
        Finds a catalog item matching the user's keyword for the given room type and preferred style.
        Returns the raw DB row as a dict, or None if not found.
        """
        cleaned = re.sub(
            r"^(?:what about|how about|what of|can we add|can we have|can you add|can i get|could we add|do you have|do we have|is there|are there|i want|i need|please add|give me|also|and|with|a|an|the|some|one|new)\s+",
            "",
            keyword.strip(),
            flags=re.IGNORECASE
        ).strip().lower()
        if not cleaned or len(cleaned) < 2:
            return None

        # Synonyms mapping
        synonyms = {
            "arm chair": "armchair",
            "armchair": "armchair",
            "arm chairs": "armchair",
            "armchairs": "armchair",
            "chair": "armchair",
            "chairs": "armchair",
            "accent chair": "armchair",
            "accent chairs": "armchair",
            "lounge chair": "armchair",
            "lounge chairs": "armchair",
            "book shelf": "bookshelf",
            "book shelves": "bookshelf",
            "bookshelf": "bookshelf",
            "bookshelves": "bookshelf",
            "bookcase": "bookshelf",
            "book case": "bookshelf",
            "center table": "coffee table",
            "tea table": "coffee table",
            "coffee table": "coffee table",
            "coffeetable": "coffee table",
            "floor lamp": "floor lamp",
            "floorlamp": "floor lamp",
            "standing lamp": "floor lamp",
            "reading lamp": "table lamp",
            "table lamp": "table lamp",
            "lamp": "floor lamp",
            "lamps": "floor lamp",
            "light": "floor lamp",
            "lights": "floor lamp",
            "lighting": "floor lamp",
            "side table": "side table",
            "sidetable": "side table",
            "end table": "side table",
            "bean bag": "bean bag",
            "beanbag": "bean bag",
            "bean bags": "bean bag",
            "plant": "planter",
            "plants": "planter",
            "planter": "planter",
            "planters": "planter",
            "greenery": "planter",
            "botanical": "planter",
            "botanicals": "planter",
            "pots": "planter",
            "pot": "planter",
            "curtain": "curtains",
            "curtains": "curtains",
            "drapes": "curtains",
            "sheers": "curtains",
            "sheer curtains": "curtains",
            "rug": "rug",
            "rugs": "rug",
            "couch": "sofa",
            "couches": "sofa",
            "sofa": "sofa",
            "sofas": "sofa",
            "sectional": "sofa",
            "closet": "wardrobe",
            "almirah": "wardrobe",
            "cupboard": "wardrobe",
            "wardrobe": "wardrobe",
            "painting": "wall art",
            "art": "wall art",
            "artwork": "wall art",
            "wall art": "wall art",
            "wallart": "wall art",
            "cushion": "cushions",
            "cushions": "cushions",
            "pillow": "cushions",
            "pillows": "cushions",
            "pouf": "ottoman",
            "pouffe": "ottoman",
            "ottoman": "ottoman",
            "tv": "tv unit",
            "television": "tv unit",
            "tv stand": "tv unit",
            "tv unit": "tv unit",
            "tv console": "tv unit",
            "media console": "tv unit",
            "entertainment unit": "tv unit"
        }
        search_term = synonyms.get(cleaned, cleaned)

        norm_room = self._normalize_room_type(room_type)
        conn = tools.get_db_connection(self.db_path)
        cursor = conn.cursor()

        # Query items for this room type, ordering in-stock items first
        cursor.execute(
            "SELECT * FROM catalog WHERE LOWER(room_types) LIKE LOWER(?) ORDER BY in_stock DESC",
            (f"%{norm_room}%",)
        )
        candidates = [dict(r) for r in cursor.fetchall()]
        conn.close()

        def norm(s: str) -> str:
            return re.sub(r"[^a-z0-9]", "", (s or "").lower())

        norm_search = norm(search_term)
        norm_search_sing = re.sub(r"(ies|es|s)$", "", norm_search)

        # 1. Exact or substring category match using normalized strings
        matching_items = []
        for item in candidates:
            cat = item["category"]
            name = item["name"]
            norm_cat = norm(cat)
            norm_name = norm(name)
            norm_cat_sing = re.sub(r"(ies|es|s)$", "", norm_cat)

            if (
                norm_search == norm_cat
                or norm_search_sing == norm_cat_sing
                or norm_search in norm_cat
                or (len(norm_cat) >= 4 and norm_cat in norm_search)
                or norm_search in norm_name
                or (len(norm_name) >= 4 and norm_name in norm_search)
            ):
                matching_items.append(item)

        if not matching_items:
            return None

        # Prefer in-stock items if available
        in_stock_matches = [it for it in matching_items if it.get("in_stock", 1) == 1]
        pool = in_stock_matches if in_stock_matches else matching_items

        # Prefer item matching requested style
        for item in pool:
            if style.lower() in (item.get("style_tags") or "").lower():
                return item

        # Prefer item where search_term is in name
        for item in pool:
            if search_term in item["name"].lower():
                return item

        # Fallback to first matching item
        return pool[0]

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
