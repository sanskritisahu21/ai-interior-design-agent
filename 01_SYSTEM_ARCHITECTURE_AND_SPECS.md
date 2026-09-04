# 01_SYSTEM_ARCHITECTURE_AND_SPECS.md
## System Architecture & Technical Specifications: Interior Design AI Agent
---
### 1. Executive Product Architecture Overview
The system is an autonomous, agentic reasoning pipeline designed for **Interior Company x Blocks**. It converts unstructured or semi-structured customer room briefs into budget-compliant, physically viable interior design plans and an itemized Bill of Quantities (BOQ).
Unlike single-shot chatbots that hallucinate products from memory, this agent operates within a **ReAct (Reasoning + Acting) loop** using three deterministic tools backed by a local SQLite database (`interior_company_catalog.db`).
```
                              ┌──────────────────────────────────────┐
                              │         Customer Room Brief          │
                              │  (Room, Dimensions, Budget, Style)   │
                              └──────────────────┬───────────────────┘
                                                 │
                                                 ▼
                              ┌──────────────────────────────────────┐
                              │       P0 Guardrail Filter Layer      │
                              │  - Out-of-Scope (Civil/Structural)   │
                              │  - Commercial Pricing/Delivery Lock  │
                              └───────────┬──────────────────┬───────┘
                                          │                  │
                           [Out of Scope] │                  │ [In Scope]
                                          ▼                  ▼
                              ┌───────────────────────┐ ┌────────────────────────────────────┐
                              │  Safe Refusal Output  │ │    ReAct Agent Orchestration Loop  │
                              │  & Expert Escalation  │ │  (Prompt + Thought-Action-Obs)     │
                              └───────────────────────┘ └─────────────────┬──────────────────┘
                                                                          │
                                  ┌───────────────────────────────────────┼───────────────────────────────────────┐
                                  ▼                                       ▼                                       ▼
                      ┌───────────────────────┐               ┌───────────────────────┐               ┌───────────────────────┐
                      │  Tool 1: Catalog DB   │               │   Tool 2: Budget Tally│               │ Tool 3: Spatial Check │
                      │  Parameterized SQL on │               │ Running cost vs cap,  │               │ Footprint ratio & 35% │
                      │  SQLite (Style, Room) │               │ remaining funds delta │               │ circulation rule      │
                      └───────────┬───────────┘               └───────────┬───────────┘               └───────────┬───────────┘
                                  │                                       │                                       │
                                  └───────────────────────────────────────┼───────────────────────────────────────┘
                                                                          │
                                                                          ▼
                                                      ┌─────────────────────────────────────────┐
                                                      │           Convergence Engine            │
                                                      │  - Fits room & budget?                  │
                                                      │  - If NO ➔ Backtrack & swap items       │
                                                      │  - If YES ➔ Format final BOQ deliverable│
                                                      └───────────────────┬─────────────────────┘
                                                                          │
                                                                          ▼
                                                      ┌─────────────────────────────────────────┐
                                                      │       Final Customer Deliverable        │
                                                      │  1. Design Rationale & Style Narrative  │
                                                      │  2. Itemized Bill of Quantities (BOQ)   │
                                                      │  3. Spatial Layout & Circulation Stats  │
                                                      │  4. Transparent Trade-off Disclosures   │
                                                      └─────────────────────────────────────────┘
```
---
### 2. Database Schema & Data Cleansing Protocol
The single source of truth is `interior_company_catalog.db`.
#### Table: `catalog` (72 Items)
* `item_id` (TEXT, PK): E.g., `SOF-001`, `CFT-002`, `TVU-001`.
* `category` (TEXT): E.g., `Sofa`, `Coffee Table`, `TV Unit`, `Rug`, `Floor Lamp`, `Pendant Light`.
* `name` (TEXT): Product marketing title.
* `style_tags` (TEXT): Comma-separated (e.g., `Scandinavian, Minimalist`, `Industrial`, `Bohemian`).
* `price_inr` (INTEGER, Nullable): Item price in INR.
* `width_cm`, `depth_cm`, `height_cm` (INTEGER, Nullable): Physical dimensions in cm.
* `color_finish` (TEXT): Finish specification.
* `in_stock` (INTEGER): `1` = Available, `0` = Out of Stock.
* `lead_time_days` (INTEGER): Delivery timeline.
* `room_types` (TEXT): Comma-separated applicability (e.g., `Living Room`, `Bedroom`).
#### Data Cleansing & Defensive Handling Rules:
1. **Unpriced Products (`price_inr IS NULL`):**
   * *Rule:* Never treat `NULL` as ₹0. Unpriced items cannot be silently added to a committed BOQ. If selected, the agent must flag them with an estimated market allowance and label the row as `Price on Request / Awaiting Vendor Quote`.
2. **Missing Dimensions (`width_cm` or `depth_cm IS NULL`):**
   * *Rule:* When dimensions are `NULL`, the tool must impute conservative median footprints by category (e.g., Side Table: $45 \times 45\text{ cm}$; Floor Lamp: $40 \times 40\text{ cm}$; Decor/Plant: $30 \times 30\text{ cm}$) and mark the item for mandatory site verification.
3. **Out-of-Stock Products (`in_stock = 0`):**
   * *Rule:* Filter out `in_stock = 0` by default. If lead time exceeds 30 days, do not include in rapid-move-in briefs unless the customer explicitly permits backorders.
---
### 3. Tool Specifications & Python Implementation Contracts
```python
import sqlite3
from typing import List, Dict, Any, Optional
DB_PATH = "interior_company_catalog.db"
def catalog_search(
    category: Optional[str] = None,
    style: Optional[str] = None,
    room_type: str = "Living Room",
    max_price: Optional[int] = None,
    in_stock_only: bool = True
) -> List[Dict[str, Any]]:
    """
    Query the SQLite catalog using parameterized filters.
    Enforces that the agent only accesses real, verified catalog items.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = "SELECT * FROM catalog WHERE room_types LIKE ?"
    params = [f"%{room_type}%"]
    if category:
        query += " AND category = ?"
        params.append(category)
    if style:
        query += " AND style_tags LIKE ?"
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
def budget_calculator(
    selected_item_ids: List[str],
    total_budget_inr: int
) -> Dict[str, Any]:
    """
    Sums selected items, compares against total budget, and reports remaining balance.
    Detects unpriced items and prevents silent over-budget spending.
    """
    if not selected_item_ids:
        return {
            "total_spent": 0,
            "remaining_budget": total_budget_inr,
            "is_over_budget": False,
            "unpriced_items": [],
            "breakdown": []
        }
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(selected_item_ids))
    cursor.execute(f"SELECT item_id, name, category, price_inr FROM catalog WHERE item_id IN ({placeholders})", selected_item_ids)
    rows = cursor.fetchall()
    conn.close()
    total_spent = 0
    unpriced = []
    breakdown = []
    for r in rows:
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
            "price": price
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
    selected_item_ids: List[str]
) -> Dict[str, Any]:
    """
    Evaluates physical fit and spatial circulation.
    Rule: Total furniture footprint must not exceed 35% of total room area.
    Ensures minimum 75cm - 90cm walkways.
    """
    room_area_sqm = (room_length_cm * room_width_cm) / 10000.0
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(selected_item_ids))
    cursor.execute(f"SELECT item_id, name, category, width_cm, depth_cm FROM catalog WHERE item_id IN ({placeholders})", selected_item_ids)
    items = cursor.fetchall()
    conn.close()
    total_footprint_sqm = 0.0
    imputed_items = []
    category_defaults = {
        "Sofa": (200, 90),
        "Coffee Table": (100, 60),
        "TV Unit": (160, 40),
        "Rug": (200, 140), # Rugs are floor coverings, discounted in clearance calculation
        "Armchair": (80, 80),
        "Floor Lamp": (40, 40),
        "Side Table": (45, 45),
        "Bookshelf": (80, 35)
    }
    for item in items:
        # Rugs do not block physical circulation height, footprint tracked separately
        if item["category"] == "Rug":
            continue
        w = item["width_cm"]
        d = item["depth_cm"]
        if w is None or d is None:
            default_w, default_d = category_defaults.get(item["category"], (50, 50))
            w = w or default_w
            d = d or default_d
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
```
---
### 4. BOQ Deliverable JSON Schema
Every successful agent execution returns this structured JSON:
```json
{
  "brief_id": "BR-01",
  "status": "SUCCESS",
  "design_concept": {
    "theme": "Calm Scandinavian Living Sanctuary",
    "palette_and_materials": "Light oak, oatmeal fabric, matte white, textured wool",
    "rationale": "Optimized for south-facing sunlight using light woods and reflective textures, maintaining calm, clutter-free circulation."
  },
  "boq": [
    {
      "item_id": "SOF-001",
      "category": "Sofa",
      "name": "Nordby 3-Seater Fabric Sofa",
      "dimensions": "210 x 88 x 82 cm",
      "finish": "Oatmeal grey",
      "price_inr": 62000,
      "in_stock": 1,
      "lead_time_days": 7
    }
  ],
  "financial_summary": {
    "budget_allocated_inr": 250000,
    "total_spent_inr": 184000,
    "remaining_budget_inr": 66000,
    "budget_utilization_percentage": 73.6
  },
  "spatial_fit_summary": {
    "room_area_sqm": 17.28,
    "furniture_footprint_sqm": 4.12,
    "occupancy_percentage": "23.8%",
    "circulation_viable": true
  },
  "trade_offs_and_omissions": [
    "Prioritized high-quality 3-seater sofa and wool rug; excluded secondary accent armchair to preserve open walking space."
  ]
}
```