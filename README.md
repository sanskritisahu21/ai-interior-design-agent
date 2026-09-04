# Autonomous AI Interior Design Agent — Interior Company x Blocks

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Zero External Dependencies](https://img.shields.io/badge/dependencies-0%20external-brightgreen.svg)]()
[![Production Ship Gate](https://img.shields.io/badge/Ship%20Gate-ALL%20PASSED%20(100%25)-success.svg)]()
[![Catalog SKU Hallucination](https://img.shields.io/badge/SKU%20Hallucination%20Rate-0.0%25-brightgreen.svg)]()
[![Civil Refusal Safety](https://img.shields.io/badge/Civil%20Refusal%20Rate-100%25-brightgreen.svg)]()

An autonomous, production-grade interior design agent built for **Interior Company x Blocks**. It converts customer room briefs into budget-compliant, physically viable interior design plans and itemized **Bills of Quantities (BOQ)** backed by verified catalog inventory in SQLite.

Unlike single-shot chatbots that hallucinate non-existent products, this agent operates within a **ReAct (Reasoning + Acting) loop** using three deterministic tools, strict P0 safety guardrails, and an automated 25-case golden evaluation harness.

---

## 🌟 Key Highlights & Ship Gate Results

- **100% Real Catalog SKUs (0.0% Hallucination):** Every single recommended item is verified via SQL against `interior_company_catalog.db`.
- **0.0% Unflagged Budget Overruns:** Continuous balance checking with strict trapping for unpriced items (`price_inr IS NULL`).
- **100% Civil & Structural Refusal:** Instant operational refusal and human escalation when customers request wall demolition, load-bearing assessments, or utility splicing.
- **35% Maximum Footprint Clearance:** Validates physical fit and guarantees minimum 75–90cm circulation corridors.
- **Zero External Dependency Guarantee:** Runs out-of-the-box in `< 1 minute` using standard Python 3 standard library (`sqlite3`, `json`, `http.server`, `urllib`).

---

## 🏗️ System Architecture & ReAct Loop

```
                             ┌──────────────────────────────────────┐
                             │         Customer Room Brief          │
                             │  (Room, Dimensions, Budget, Style)   │
                             └──────────────────┬───────────────────┘
                                                │
                                                ▼
                             ┌──────────────────────────────────────┐
                             │       P0 Guardrail Filter Layer      │
                             │  - Civil / Structural Hazard Refusal │
                             │  - Commercial SLA & Pricing Lock     │
                             │  - Zero / Negative Budget Trap       │
                             └───────────┬──────────────────┬───────┘
                                         │                  │
                          [Out of Scope] │                  │ [In Scope]
                                         ▼                  ▼
                             ┌───────────────────────┐ ┌────────────────────────────────────┐
                             │  Safe Refusal Output  │ │    ReAct Agent Orchestration Loop  │
                             │  & Expert Escalation  │ │  (Thought ➔ Action ➔ Observation)  │
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

## ⚡ Quickstart (< 1 Minute Setup)

No third-party packages or API keys required. Python 3.9+ standard library is 100% self-sufficient.

### 1. Run the Full 25-Case Golden Evaluation Harness
```bash
python run_evals.py
```
*Evaluates all 25 test cases, prints the Production Ship Gate Scorecard, and writes `eval_report.md`.*

### 2. Run CLI Brief Runner
```bash
# Baseline Scandinavian living room (BR-01)
python run_app.py --brief BR-01

# Civil safety refusal test (BR-07: wall demolition query)
python run_app.py --brief BR-07

# Budget deficit transparent trade-off test (BR-06: ₹45,000 cap)
python run_app.py --brief BR-06
```

### 3. Launch the Interactive Web Application
```bash
python run_app.py --serve
```
*Open [http://localhost:8080](http://localhost:8080) in your browser. Select any of the 14 preset database briefs or build custom room briefs.*

---

## 📊 Production Ship Gate Scorecard

Results generated across the complete 25-case golden set:

| Evaluation Metric | Ship Gate Threshold | Actual Result | Severity | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Catalog SKU Hallucination Rate** | 0.0% (100% verified) | **0.0%** | P0 - Launch Blocker | ✅ **PASS** |
| **Unflagged Budget Overrun Rate** | 0.0% (100% verified) | **0.0%** | P0 - Launch Blocker | ✅ **PASS** |
| **Civil / Safety Refusal Rate** | 100% Pass | **100.0%** | P0 - Launch Blocker | ✅ **PASS** |
| **Spatial Circulation Fit (<= 35%)** | >= 95% Pass | **96.0% (24/25)** | P1 - Critical Defect | ✅ **PASS** |
| **Behavioral Tool Audit Invocation** | >= 95% Pass | **100.0%** | P1 - Critical Defect | ✅ **PASS** |
| **LLM Judge Style Coherence Avg** | >= 4.0 / 5.0 | **5.0 / 5.0** | P2 - Quality Target | ✅ **PASS** |

### Subjective Quality Rubric
- **Style Coherence:** `5.0 / 5.0`
- **Rationale Quality:** `4.72 / 5.0`
- **Trade-off Transparency:** `4.56 / 5.0`
- **Composite Score:** `4.76 / 5.0`

---

## 🛠️ Repository Structure

```
├── tools.py                # 3 Deterministic tools (catalog_search, budget_calculator, layout_fit_check)
├── guardrails.py           # P0 Guardrails (Civil safety, SLA lock, zero budget, spatial limits)
├── agent.py                # Autonomous ReAct agent & BOQ generator
├── golden_test_cases.json  # 25-case golden test set (14 DB briefs, 6 adversarial, 5 guardrails)
├── run_evals.py            # Automated evaluation harness & markdown scorecard generator
├── run_app.py              # Runnable MVP interface (Interactive Web App & CLI)
├── decision_log.md         # Deliverable C: One-page product decision log
├── eval_report.md          # Generated evaluation scorecard report
├── requirements.txt        # Zero external dependencies specification
└── interior_company_catalog.db  # SQLite database (catalog & room_briefs tables)
```

---

## 🛡️ The 5 Core Product Guardrails

1. **P0 Civil & Structural Safety:** Detects inquiries regarding knocking down walls, load-bearing assessments, or utility routing (`BR-07`, `SYN-07`, `SYN-08`). Halts execution with status `CIVIL_SAFETY_REFUSAL` and refers customer to a licensed structural engineer / architect.
2. **P0 Commercial & SLA Lock:** Intercepts requests demanding guaranteed delivery dates or unauthorized commercial discounts (`BR-10`, `SYN-09`). Status: `SLA_PRICING_REFUSAL`.
3. **Zero / Negative Budget Interception:** Detects non-viable procurement budgets (`SYN-05`, `SYN-11`). Status: `IMPOSSIBLE_BUDGET_REFUSAL`.
4. **Spatial Overcrowding Prevention:** Enforces that loose furniture footprint never exceeds 35% of floor area (`BR-09`, `SYN-06`).
5. **Catalog Boundary & Brand Substitution:** Intercepts external designer brands (Togo, Noguchi, Eames, IKEA) and transparently substitutes closest stylistic catalog equivalents with zero hallucination (`BR-08`, `SYN-10`).

---

## 📜 Deliverable C Summary (Decision Log Highlights)

- **Living Room Vertical Slice:** Living rooms represent 45–55% of loose furniture procurement budgets and carry the highest constraint density. Focusing on living rooms captures maximum GMV with rigorous circulation validation.
- **35% Footprint Rule:** Chosen over heavy 3D rendering engines to deliver 90% of circulation validation value with zero runtime rendering lag.
- **AI Tool Steering:** Intervened to prevent the "eager-to-please" structural safety hazard and patched the silent `NULL` price leakage trap (`price_inr IS NULL`).
- **Post-MVP Roadmap:**
  - **v1.1:** Multi-modal 2D architectural CAD & smartphone LiDAR scan input.
  - **v1.2:** Real-time SAP/ERP inventory sync with 15-minute soft reservation locks.
  - **v1.3:** Automated designer-in-the-loop escalation tickets for edge cases.

---

## 🤝 Authors & Credits
Developed for the **Interior Company x Blocks** Associate Product Manager Build Challenge.
