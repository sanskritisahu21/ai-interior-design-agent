# AI Interior Design Agent - Implementation Plan

Building the autonomous AI Interior Design Agent for **Interior Company x Blocks**, implementing the 3 deterministic tools, ReAct reasoning loop, P0 guardrails, 25-case golden test evaluation harness, and decision log.

---

## User Review Required

> [!IMPORTANT]
> **Zero External Dependency Guarantee**: The application and evaluation harness will run out-of-the-box using standard Python 3 (sqlite3, json, http.server, urllib) without requiring complex third-party pip dependencies or API keys. If optional packages (`pydantic`, `streamlit`) are installed, they will be seamlessly leveraged, but standard Python is 100% self-sufficient and runnable in under 1 minute.

> [!NOTE]
> **Defensible Living Room Vertical Slice**: In accordance with `04_DECISION_LOG_AND_SUBMISSION_GUIDE.md`, the system is deeply optimized for residential living rooms (the highest constraint density and largest share of procurement budgets), while also supporting bedroom, dining, and study briefs present in the database.

---

## Proposed Architectural Components

### 1. Deterministic Core Tools (`tools.py`)
Implements the exact function signatures and contracts specified in `01_SYSTEM_ARCHITECTURE_AND_SPECS.md`:
1. **`catalog_search(category, style, room_type, max_price, in_stock_only)`**:
   - Parameterized SQL execution on `interior_company_catalog.db`.
   - Filters on `room_types LIKE ?`, `category = ?`, `style_tags LIKE ?`, `price_inr <= ? OR price_inr IS NULL`, and `in_stock = 1`.
   - Defensive data handling: excludes out-of-stock items by default, permits null-price items only with explicit quote flags.
2. **`budget_calculator(selected_item_ids, total_budget_inr)`**:
   - Queries `catalog` for prices, computes exact sum `total_spent`, `remaining_budget`, `is_over_budget`, and `overage_amount`.
   - Traps `NULL` prices: adds item to `unpriced_items`, flags row as requiring vendor quotation, and prevents silent zero-cost leakage.
3. **`layout_fit_check(room_length_cm, room_width_cm, selected_item_ids)`**:
   - Calculates `room_area_sqm = (length * width) / 10000.0`.
   - Excludes `Rug` category from physical obstruction clearance.
   - Applies conservative median footprint imputations when width or depth is `NULL` (e.g. Sofa: 200x90, Coffee Table: 100x60, TV Unit: 160x40, Armchair: 80x80, Floor Lamp: 40x40, Side Table: 45x45, Bookshelf: 80x35).
   - Validates the 35% maximum furniture coverage threshold (`occupancy_ratio <= 0.35`). Returns clearance metrics and blockage warnings.

### 2. Guardrails & Safety Filter Layer (`guardrails.py`)
Implements the 5 Core Product Guardrails from `02_GUARDRAILS_AND_EDGE_CASES.md`:
- **P0 Civil & Structural Safety**: Detects inquiries regarding knocking down walls, load-bearing assessment, plumbing duct relocation, electrical conduit splicing. Emits immediate hard operational refusal referring customer to licensed structural engineers / architects.
- **P0 Commercial & SLA Lock**: Intercepts requests demanding guaranteed delivery dates or unauthorized discounts. Clarifies logistics lead times and routes commercial negotiation to human sales operations.
- **Budget Integrity Filter**: Intercepts negative or zero budgets (`IMPOSSIBLE_BUDGET_REFUSAL`), detects budget deficit (`BUDGET_DEFICIT_FLAGGED`), prioritizes foundational furniture, and outputs honest trade-off disclosures.
- **Spatial Overcrowding Filter**: Intercepts impossible room dimensions or micro-spaces where requested furniture exceeds 35% footprint (`SPATIAL_OVERCROWDING_REFUSAL`).
- **Catalog Substitution Protocol**: Detects external designer brands (Togo, Noguchi, Eames, IKEA, Herman Miller), explains catalog boundaries, and substitutes stylistic catalog equivalents.

### 3. ReAct Agent & Convergence Engine (`agent.py`)
- Executes the ReAct loop: **Thought -> Action (Tool Call) -> Observation -> Next Step**.
- Tracks detailed audit logs of all tool calls (`catalog_search`, `budget_calculator`, `layout_fit_check`).
- Solves room briefs iteratively:
  1. Identifies required categories from `must_haves` and style from `style_preference`.
  2. Queries catalog via `catalog_search` for candidate SKUs.
  3. Verifies running cost via `budget_calculator`. Backtracks if budget is exceeded.
  4. Verifies spatial clearance via `layout_fit_check`. Backtracks if occupancy > 35%.
  5. Assembles the final standardized BOQ Deliverable JSON matching Section 4 schema:
     - `brief_id`
     - `status` (`SUCCESS`, `CIVIL_SAFETY_REFUSAL`, `SLA_PRICING_REFUSAL`, `SPATIAL_OVERCROWDING_REFUSAL`, `BUDGET_DEFICIT_FLAGGED`, `CATALOG_SUBSTITUTION`)
     - `design_concept` (`theme`, `palette_and_materials`, `rationale`)
     - `boq` (itemized list with real SKUs, specs, dimensions, finishes, lead times, prices)
     - `financial_summary` (`budget_allocated_inr`, `total_spent_inr`, `remaining_budget_inr`, `budget_utilization_percentage`)
     - `spatial_fit_summary` (`room_area_sqm`, `furniture_footprint_sqm`, `occupancy_percentage`, `circulation_viable`)
     - `trade_offs_and_omissions` (explicit transparent trade-offs)

### 4. 25-Case Golden Test Set & Eval Harness (`run_evals.py`, `golden_test_cases.json`)
- Embeds the complete 25-case golden set across Category A (14 database briefs), Category B (6 synthetic adversarial cases), and Category C (5 guardrail and refusal cases).
- Evaluates:
  1. **Catalog SKU Integrity** (100% real items, 0 hallucinated SKUs).
  2. **Budget Compliance** (Total spent <= budget, unflagged budget overrun = 0).
  3. **Spatial Clearance** (<= 35% footprint occupancy).
  4. **Guardrail Interception** (Correct refusal status for civil, SLA, micro-space, zero/negative budget).
  5. **Behavioral Tool Audit** (Verifies tools were actively called in the reasoning loop).
  6. **Subjective Scoring Rubric** (Style Coherence 1-5, Rationale Quality 1-5, Trade-off Transparency 1-5).
- Generates a production **Ship Gate** scorecard report and saves it to `eval_report.md`.

### 5. Runnable MVP Web & CLI Interface (`run_app.py`)
- Clean, fast interactive web UI and CLI:
  - Supports running any of the 14 preset briefs (BR-01 through BR-14) or inputting custom briefs.
  - Displays live reasoning steps, tool calls, spatial breakdown, budget progress bar, and formatted BOQ table.
  - Zero setup required: runs immediately with `python run_app.py`.

### 6. Submission Documentation & Decision Log
- `decision_log.md`: One-page product decision log as detailed in `04_DECISION_LOG_AND_SUBMISSION_GUIDE.md`.
- `README.md`: Comprehensive instructions, architecture diagram, usage guide, and test steps.
- `requirements.txt`: Clean dependency definition.

---

## Proposed Changes

### Core System Files

#### [NEW] [tools.py](file:///d:/AI%20Agent%20for%20Interior%20Designing/tools.py)
The 3 deterministic tools (`catalog_search`, `budget_calculator`, `layout_fit_check`) with SQLite integration and defensive handling.

#### [NEW] [guardrails.py](file:///d:/AI%20Agent%20for%20Interior%20Designing/guardrails.py)
P0 guardrail rules, civil engineering safety refusal, commercial SLA lock, budget bounds, and designer brand substitution logic.

#### [NEW] [agent.py](file:///d:/AI%20Agent%20for%20Interior%20Designing/agent.py)
ReAct orchestration engine, brief interpreter, iterative convergence engine, tool-use tracking, and BOQ deliverable generator.

#### [NEW] [golden_test_cases.json](file:///d:/AI%20Agent%20for%20Interior%20Designing/golden_test_cases.json)
The complete 25-case golden test set (TC-01 through TC-25) specified in `03_EVAL_HARNESS_SCORERS_AND_TEST_CASES.md`.

#### [NEW] [run_evals.py](file:///d:/AI%20Agent%20for%20Interior%20Designing/run_evals.py)
The complete automated evaluation harness, 5 deterministic scorers, subjective rubric scorer, and markdown report generator.

#### [NEW] [run_app.py](file:///d:/AI%20Agent%20for%20Interior%20Designing/run_app.py)
Runnable MVP interface featuring both CLI mode and an interactive web demo.

#### [NEW] [decision_log.md](file:///d:/AI%20Agent%20for%20Interior%20Designing/decision_log.md)
One-page product decision log (Deliverable C).

#### [NEW] [README.md](file:///d:/AI%20Agent%20for%20Interior%20Designing/README.md)
Complete user guide, architecture documentation, and run instructions (<5 mins).

#### [NEW] [requirements.txt](file:///d:/AI%20Agent%20for%20Interior%20Designing/requirements.txt)
Dependencies file.

---

## Verification Plan

### Automated Tests
1. **Tool Unit Tests**: Verify `catalog_search`, `budget_calculator`, and `layout_fit_check` independently against edge cases (NULL price, NULL dimensions, out-of-stock items, empty inputs).
2. **Evaluation Harness**: Run `python run_evals.py` on all 25 Golden Test Cases:
   - Category A (TC-01 to TC-14): Database Briefs
   - Category B (TC-15 to TC-20): Synthetic Adversarial Cases
   - Category C (TC-21 to TC-25): Hard Guardrail & Refusal Cases
3. **Production Ship Gate Verification**: Ensure:
   - Catalog SKU Hallucination Rate: 0.0%
   - Unflagged Budget Overrun Rate: 0.0%
   - Civil / Safety Refusal Rate: 100%
   - Spatial Circulation Fit (<= 35%): >= 95%
   - Behavioral Tool Audit: >= 95%
   - Average Style Coherence Rubric Score: >= 4.0 / 5.0

### Manual & Interactive Verification
1. Run `python run_app.py --brief BR-01` to test the baseline happy path.
2. Run `python run_app.py --brief BR-07` to test the civil/structural safety hard refusal.
3. Run `python run_app.py --brief BR-06` to verify budget deficit flagging and trade-off generation.
4. Launch the local web server via `python run_app.py --serve` and test interactive room brief generation in the browser.
