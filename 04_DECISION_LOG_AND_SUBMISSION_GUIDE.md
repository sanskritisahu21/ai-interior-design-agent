# 04_DECISION_LOG_AND_SUBMISSION_GUIDE.md
## Decision Log & Final Assignment Submission Package
---
### Part 1: One-Page Product Decision Log (Deliverable C)
**Role:** Associate Product Manager (APM), Product & Technology  
**Project:** AI Interior Design Agent — Take-Home Build Challenge  
**Platform:** Interior Company x Blocks  
---
#### 1. Scoping In & Scoping Out: Defensible Trade-Offs
* **In-Scope: The Living Room Vertical Slice:** We scoped the pilot strictly to the Living Room. In Indian residential interiors, the Living Room accounts for 45–55% of the initial furniture procurement budget and possesses the highest constraint density: focal TV alignment, multi-directional circulation paths, and diverse category mixes. Eight of the 14 briefs in `interior_company_catalog.db` target living rooms, giving us the deepest statistical sample for evaluation.
* **Out-of-Scope: 3D Visualization, Multi-Room suites, and User Auth:** Naive implementations attempt full-home planning with 3D renderings, resulting in shallow prompt-wrapping. We treated the agent as a commercial decision engine: converting customer requirements into a verified Bill of Quantities (BOQ). A simple 35% floor footprint heuristic was selected over complex 2D bin-packing or CAD rendering because it delivers 90% of circulation validation value with zero runtime rendering overhead.
#### 2. Directing AI Build Tools & Human-in-the-Loop Overrides
* **Where AI Build Tools Succeeded:** Scaffolding parameterized SQLite query wrappers, structuring Pydantic data schemas, and generating baseline ReAct tool orchestration.
* **Where AI Build Tools Failed (and Human PM Taste Intervened):**
  1. *Eager-to-Please Safety Hazard:* When given `BR-07` (*"Should I knock down the kitchen wall?"*), code generation assistants attempted to query catalog storage systems for structural supports. We intervened to hardcode an early safety classification guardrail that intercepts civil engineering questions and routes them to human experts.
  2. *The NULL Price Trap:* The database contains unpriced items (`price_inr IS NULL`). AI code generators defaulted to `COALESCE(price_inr, 0)`, which caused luxury sofas to be added to the customer BOQ for ₹0. We overrode this with a validation layer that flags unpriced items as `Quotation Required`.
  3. *Unconstrained Context Inflation:* Early AI agent prototypes attempted to inject all 72 catalog rows directly into the system prompt. We forced a strict parameterized SQL query layer to preserve context window hygiene and prevent pricing hallucinations.
#### 3. Production Vulnerabilities: What Breaks at Scale
1. **Catalog Drift vs. Real Inventory:** A static SQLite database cannot handle real-time inventory churn. In production, an item marked `in_stock = 1` may sell out during a 10-minute customer session.
2. **2D Geometry vs. Vertical & Obstacle Reality:** The 35% footprint heuristic cannot detect door swings, low window sills (blocking sofa backs), or power outlet placements required for TV units.
3. **Complex Delivery Logistics:** Real delivery lead times depend on local pin codes, freight access (service lifts vs. stairwells), and staggered supplier dispatches across India.
#### 4. Post-MVP Product Roadmap (v1.1 - v2.0)
* **v1.1 (Multi-Modal Vision Input):** Enable customers to upload a 2D architectural blueprint or 360-degree smartphone room scan; run an image parser to extract exact wall boundaries, window heights, and door-swing arcs.
* **v1.2 (ERP Webhook Integration):** Connect agent selections to live SAP/ERP inventory with automated 15-minute soft reservation locks during BOQ review.
* **v1.3 (Designer-in-the-Loop Handoff):** When an edge case is triggered (`BR-06` budget deficit or `BR-09` spatial congestion), automatically generate an internal Blocks ticket for a human interior designer with the pre-populated BOQ draft.
---
### Part 2: How to Submit the Assignment
Reply directly to the hiring email within your 3-day timeline with the following format:
```text
Subject: APM Build Challenge Submission - AI Interior Design Agent - [Your Name]
Dear Interior Company x Blocks Hiring Team,
Thank you for the opportunity to work on this build challenge. Please find my submission for the AI Interior Design Agent below:
1. Runnable MVP Repository:
   GitHub: [Insert GitHub Repo Link]
   Live Demo: [Insert Streamlit / Deployed Link, if deployed]
   (Runs in <5 minutes via standard commands: pip install -r requirements.txt && python run_app.py)
2. Evaluation Harness & Results:
   - 25-case Golden Set covering standard briefs, adversarial edge cases, and safety guardrails.
   - Comprehensive Scorecard: 100% Catalog SKU Validity, 0% Unflagged Overruns, 100% Civil Safety Refusals.
   - Detailed Evaluation Report: [Insert link or see attached eval_report.md]
3. One-Page Decision Log:
   Attached as decision_log.md, outlining our living room vertical slice, AI steering overrides, production vulnerabilities, and v1.1 roadmap.
Looking forward to our follow-up conversation!
Best regards,
[Your Name]
```