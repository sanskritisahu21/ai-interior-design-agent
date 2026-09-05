# Conversational AI Interior Design Consultant ("Siya") — Implementation Plan

Building the user-driven conversational chat system led by **Siya**, featuring decoupled specialized agents, real-time database session persistence, unit conversion, catalog verification, budget reasoning, and an interactive chat UI.

---

## User Review Required

> [!IMPORTANT]
> **Exact Conversational Script Compliance**: The dialogue manager strictly enforces Siya's defined persona and response triggers:
> 1. **Greeting:** `"Hi, I am Siya, your interior design consultant!"`
> 2. **Room Type Gate:** If user is confused or says "I don't know", Siya responds: `"Sorry, I can't design without room type."`
> 3. **Dimensions Gate:** Parses mixed units (m, cm, feet/inches) and accumulates dimensions across turns (e.g., L*B first, H later). If user says "I don't know", Siya responds: `"Sorry, we need length, breadth, and height; we can't make an interior design plan without it."`
> 4. **Budget Flexibility:** Handles "more than X", "less than X", "between X and Y", or exact values. If user has no budget or is confused, gracefully skips without blocking.
> 5. **Style Verification:** Validates against DB styles. If unsupported: `"We don't have this style currently. Do you want to try from [Style 1, Style 2, Style 3] styles?"` (suggests 2-4 DB styles).
> 6. **Must-Haves & Substitution:** Suggests DB items for the room. If an unlisted item is requested: `"Currently we don't have [item] from the must-haves"` and recommends similar in-catalog pieces.
> 7. **Constraint & Plan Synthesis:** Runs catalog search, budget calculator, and layout fit check. If over budget, explains the specific reason, recommends budget-friendly swaps, and edits the plan.

---

## Proposed System Architecture

```
                               ┌──────────────────────────────────────────────┐
                               │           User Chat Interaction             │
                               │   ("Hi" / "Living Room" / "15x12 ft" / ...)  │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │         Conversation Agent ("Siya")          │
                               │  - Stage & State Machine Management          │
                               │  - Unit Parser (m, ft, in ➔ cm)              │
                               │  - Real-Time SQLite Session & Chat Logger    │
                               └──────┬───────────────┬───────────────┬───────┘
                                      │               │               │
                     ┌────────────────┘               │               └────────────────┐
                     ▼                                ▼                                ▼
         ┌───────────────────────┐        ┌───────────────────────┐        ┌───────────────────────┐
         │     Catalog Agent     │        │     Budget Agent      │        │     Layout Agent      │
         │  - Real-time DB check │        │  - Range parsing      │        │  - 35% footprint rule │
         │  - Style validation   │        │  - Overage detection  │        │  - Clearance corridors│
         │  - Item substitution  │        │  - Cost trade-offs    │        │  - Median imputation  │
         └───────────┬───────────┘        └───────────┬───────────┘        └───────────┬───────────┘
                     │                                │                                │
                     └────────────────────────────────┼────────────────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │        SQLite Database Persistence           │
                               │  - chat_sessions (dimensions, budget, state) │
                               │  - chat_messages (turn history & tool logs)  │
                               │  - catalog & room_briefs (source of truth)   │
                               └──────────────────────────────────────────────┘
```

---

## Proposed Changes

### 1. Multi-Agent Decoupled Modules (`agents/`)

Each agent will be an independent, self-contained Python module so you can edit, fine-tune, or extend any one of them independently:

#### [NEW] [`agents/__init__.py`](file:///d:/AI%20Agent%20for%20Interior%20Designing/agents/__init__.py)
Package entry point exposing `CatalogAgent`, `BudgetAgent`, `LayoutAgent`, and `ConversationAgent`.

#### [NEW] [`agents/catalog_agent.py`](file:///d:/AI%20Agent%20for%20Interior%20Designing/agents/catalog_agent.py)
- Retrieves distinct styles and categories directly from `catalog`.
- Validates user-requested styles and suggests 2–4 verified DB styles if unsupported.
- Detects whether requested must-haves exist in DB, alerts user if missing (`"Currently we don't have [item] from the must-haves"`), and finds closest in-catalog substitutes.
- Filters by room type, stock status, and client constraints.

#### [NEW] [`agents/budget_agent.py`](file:///d:/AI%20Agent%20for%20Interior%20Designing/agents/budget_agent.py)
- Parses natural language budget expressions: `"under 2L"`, `"less than 150000"`, `"more than 50k"`, `"between 1L and 2L"`, `"2.5 lakhs"`.
- Checks running item totals, detects over-budget conditions, identifies the specific items driving the overrun, and proposes affordable swaps.

#### [NEW] [`agents/layout_agent.py`](file:///d:/AI%20Agent%20for%20Interior%20Designing/agents/layout_agent.py)
- **Unit Conversion Engine:** Normalizes inputs in meters, feet, inches, or centimeters into standardized cm:
  - `m` / `meter` / `meters` ➔ `value * 100`
  - `ft` / `feet` / `'` ➔ `value * 30.48`
  - `in` / `inches` / `"` ➔ `value * 2.54`
- **Partial Dimension Accumulator:** Assembles length, breadth, and height across conversational turns (e.g. user sends `14x12 ft` first, and `10 ft height` in the next message).
- Calculates floor area and enforces the 35% safe circulation threshold (`occupancy_ratio <= 0.35`).

#### [NEW] [`agents/conversation_agent.py`](file:///d:/AI%20Agent%20for%20Interior%20Designing/agents/conversation_agent.py)
- Manages Siya's multi-step conversational state machine:
  1. `GREETING`
  2. `ROOM_TYPE` (Strict refusal if unknown: `"Sorry, I can't design without room type."`)
  3. `DIMENSIONS` (Strict refusal if unknown: `"Sorry, we need length, breadth, and height; we can't make an interior design plan without it."`)
  4. `BUDGET` (Optional/Skipped if user is confused/has no budget)
  5. `STYLE` (Suggests 2-4 DB styles if unknown)
  6. `MUST_HAVES` (Alerts if item missing, suggests DB alternatives)
  7. `PLAN_SYNTHESIS` (Executes tools and returns interactive BOQ + Trade-offs)
  8. `PLAN_REVISION` (Refines based on user feedback or budget adjustments)
- Manages real-time logging to SQLite database tables.

---

### 2. Database Schema Expansion (`db.py` & `interior_company_catalog.db`)

#### [NEW] [`db.py`](file:///d:/AI%20Agent%20for%20Interior%20Designing/db.py)
Provides thread-safe SQLite connection handling and session management:
- **`chat_sessions` Table:**
  - `session_id` (TEXT PRIMARY KEY)
  - `stage` (TEXT)
  - `room_type`, `length_cm`, `width_cm`, `height_cm` (REAL)
  - `budget_min`, `budget_max` (REAL)
  - `style`, `must_haves`, `constraints`, `notes` (TEXT)
  - `current_plan_json` (TEXT)
  - `created_at`, `updated_at` (TEXT)
- **`chat_messages` Table:**
  - `id` (INTEGER PK AUTOINCREMENT)
  - `session_id` (TEXT)
  - `sender` (TEXT: `user` | `siya` | `system`)
  - `message` (TEXT)
  - `metadata_json` (TEXT: suggested quick-replies, active tool cards, item chips)
  - `timestamp` (TEXT)

---

### 3. Interactive Chat Interface ([`run_app.py`](file:///d:/AI%20Agent%20for%20Interior%20Designing/run_app.py))

Update `run_app.py` to add a **Full-Screen Chat UI**:
- Chat with **Siya** in real-time with typing indicator and message history.
- Dynamic quick-reply chips (e.g. `Living Room`, `Scandinavian`, `Suggest Must-Haves`, `Skip Budget`).
- Embedded interactive BOQ cards and budget meter right inside the chat stream.
- Side drawer to inspect the live session state in the database.

---

## Verification Plan

### Automated Dialogue Tests
1. **Unit Parser Tests:** Verify that `"15x12 ft"`, `"4.5m by 3.8m"`, `"height 9 feet"`, and `"450 x 360 x 290 cm"` correctly normalize to cm.
2. **Dialogue Gate Tests:**
   - Test "Hi" ➔ prompts room type.
   - Test "I don't know" on room type ➔ verifies `"Sorry, I can't design without room type."` refusal.
   - Test "I don't know" on dimensions ➔ verifies `"Sorry, we need length, breadth, and height..."` refusal.
   - Test "I don't know" on budget ➔ verifies graceful skip.
   - Test unsupported style (e.g., "Gothic Victorian") ➔ verifies `"We don't have this style currently..."` and 2–4 suggested DB styles.
   - Test unlisted must-have (e.g., "Togo Sofa") ➔ verifies `"Currently we don't have Togo Sofa from the must-haves"` + catalog alternatives.
   - Test budget deficit ➔ verifies explanation and budget-friendly substitutions.
3. **Database Logging Tests:** Verify that every user and Siya message is inserted into `chat_sessions` and `chat_messages`.

### Manual & Interactive Verification
- Launch `python run_app.py --serve` and complete a full conversational design session in the browser.
