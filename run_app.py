"""
run_app.py - Runnable MVP Application (Interactive Web UI & CLI)
Autonomous AI Interior Design Agent for Interior Company x Blocks.

Usage:
  CLI Mode:
    python run_app.py --brief BR-01
    python run_app.py --brief BR-07
    python run_app.py --eval

  Interactive Web UI:
    python run_app.py --serve
    python run_app.py --port 8080
"""

import argparse
import http.server
import json
import os
import socketserver
import sys
import urllib.parse
from typing import Dict, Any, Optional

import tools
from agent import InteriorDesignAgent

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Interior Company x Blocks — AI Interior Design Agent</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-base: #0a0e17;
      --bg-surface: #111827;
      --bg-card: #162032;
      --bg-glass: rgba(22, 32, 50, 0.75);
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-accent: rgba(99, 102, 241, 0.35);
      --primary: #6366f1;
      --primary-glow: rgba(99, 102, 241, 0.25);
      --primary-hover: #4f46e5;
      --accent-gold: #f59e0b;
      --accent-emerald: #10b981;
      --accent-rose: #f43f5e;
      --accent-sky: #0ea5e9;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --radius-sm: 8px;
      --radius-md: 14px;
      --radius-lg: 20px;
      --shadow-sm: 0 4px 12px rgba(0, 0, 0, 0.3);
      --shadow-lg: 0 12px 36px rgba(0, 0, 0, 0.45);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg-base);
      color: var(--text-main);
      font-family: 'Plus Jakarta Sans', sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      line-height: 1.6;
      background-image: 
        radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 85% 85%, rgba(14, 165, 233, 0.06) 0%, transparent 40%);
    }

    /* Top Navigation Header */
    header {
      background: rgba(10, 14, 23, 0.85);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border-subtle);
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 16px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }

    .brand-logo {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, var(--primary), var(--accent-sky));
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      font-weight: 700;
      color: #fff;
      box-shadow: 0 0 16px var(--primary-glow);
    }

    .brand-text h1 {
      font-family: 'Space Grotesk', sans-serif;
      font-size: 19px;
      font-weight: 700;
      letter-spacing: -0.5px;
      color: var(--text-main);
    }

    .brand-text p {
      font-size: 12px;
      color: var(--text-muted);
    }

    .header-badges {
      display: flex;
      gap: 10px;
      align-items: center;
    }

    .badge {
      font-size: 11px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .badge-primary {
      background: rgba(99, 102, 241, 0.15);
      color: #818cf8;
      border: 1px solid rgba(99, 102, 241, 0.3);
    }

    .badge-success {
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.3);
    }

    /* Main Container Grid */
    main {
      flex: 1;
      max-width: 1540px;
      width: 100%;
      margin: 0 auto;
      padding: 28px 32px;
      display: grid;
      grid-template-columns: 420px 1fr;
      gap: 28px;
    }

    @media (max-width: 1024px) {
      main {
        grid-template-columns: 1fr;
      }
    }

    /* Left Control Sidebar */
    .sidebar {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 22px;
      box-shadow: var(--shadow-sm);
    }

    .card-title {
      font-family: 'Space Grotesk', sans-serif;
      font-size: 15px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--text-muted);
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .form-group {
      margin-bottom: 14px;
    }

    .form-group label {
      display: block;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    select, input, textarea {
      width: 100%;
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 10px 14px;
      color: var(--text-main);
      font-family: inherit;
      font-size: 13px;
      outline: none;
      transition: all 0.2s ease;
    }

    select:focus, input:focus, textarea:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px var(--primary-glow);
    }

    .dim-grid {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 8px;
    }

    .btn-run {
      width: 100%;
      background: linear-gradient(135deg, var(--primary), #4338ca);
      color: #fff;
      border: none;
      border-radius: var(--radius-sm);
      padding: 14px;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      box-shadow: 0 4px 18px var(--primary-glow);
      transition: all 0.2s ease;
      margin-top: 10px;
    }

    .btn-run:hover {
      background: linear-gradient(135deg, #4f46e5, #3730a3);
      transform: translateY(-1px);
      box-shadow: 0 6px 22px rgba(99, 102, 241, 0.4);
    }

    .btn-run:active {
      transform: translateY(0);
    }

    /* Right Output Workspace */
    .workspace {
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    /* Status Banner */
    .status-banner {
      padding: 16px 20px;
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: space-between;
      border: 1px solid transparent;
      box-shadow: var(--shadow-sm);
      animation: fadeIn 0.3s ease;
    }

    .status-success {
      background: rgba(16, 185, 129, 0.12);
      border-color: rgba(16, 185, 129, 0.3);
      color: #34d399;
    }

    .status-warning {
      background: rgba(245, 158, 11, 0.12);
      border-color: rgba(245, 158, 11, 0.3);
      color: #fbbf24;
    }

    .status-refusal {
      background: rgba(244, 63, 94, 0.12);
      border-color: rgba(244, 63, 94, 0.3);
      color: #fb7185;
    }

    .status-substitution {
      background: rgba(14, 165, 233, 0.12);
      border-color: rgba(14, 165, 233, 0.3);
      color: #38bdf8;
    }

    .status-left {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 14px;
      font-weight: 600;
    }

    .status-pill {
      padding: 4px 12px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 700;
      background: rgba(0, 0, 0, 0.25);
    }

    /* Metric Counters */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
    }

    @media (max-width: 800px) {
      .metrics-grid {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    .metric-box {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .metric-label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      color: var(--text-muted);
      letter-spacing: 0.5px;
    }

    .metric-value {
      font-family: 'Space Grotesk', sans-serif;
      font-size: 24px;
      font-weight: 700;
      color: var(--text-main);
    }

    .metric-sub {
      font-size: 12px;
      color: var(--text-dim);
    }

    /* Concept Card */
    .concept-hero {
      background: linear-gradient(135deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.9));
      border: 1px solid var(--border-accent);
      border-radius: var(--radius-md);
      padding: 24px;
      position: relative;
      overflow: hidden;
    }

    .concept-hero::before {
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, var(--primary), var(--accent-sky));
    }

    .concept-theme {
      font-family: 'Space Grotesk', sans-serif;
      font-size: 20px;
      font-weight: 700;
      color: var(--text-main);
      margin-bottom: 8px;
    }

    .concept-palette {
      display: inline-block;
      background: rgba(99, 102, 241, 0.12);
      border: 1px solid rgba(99, 102, 241, 0.25);
      color: #a5b4fc;
      font-size: 12px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: var(--radius-sm);
      margin-bottom: 12px;
    }

    .concept-rationale {
      font-size: 14px;
      color: #cbd5e1;
      line-height: 1.6;
    }

    /* BOQ Table */
    .table-container {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      overflow-x: auto;
      box-shadow: var(--shadow-sm);
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      text-align: left;
    }

    th {
      background: rgba(17, 24, 39, 0.85);
      padding: 14px 16px;
      color: var(--text-muted);
      font-weight: 600;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      border-bottom: 1px solid var(--border-subtle);
    }

    td {
      padding: 14px 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      color: var(--text-main);
      vertical-align: middle;
    }

    tr:last-child td {
      border-bottom: none;
    }

    tr:hover td {
      background: rgba(255, 255, 255, 0.02);
    }

    .sku-tag {
      font-family: monospace;
      font-size: 12px;
      font-weight: 700;
      background: rgba(255, 255, 255, 0.06);
      padding: 3px 8px;
      border-radius: 4px;
      color: #e2e8f0;
    }

    .stock-badge {
      font-size: 11px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 9999px;
    }

    .stock-in {
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
    }

    .stock-out {
      background: rgba(245, 158, 11, 0.15);
      color: #fbbf24;
    }

    /* ReAct Reasoning Accordion */
    .accordion-header {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 16px 20px;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-family: 'Space Grotesk', sans-serif;
      font-size: 14px;
      font-weight: 700;
      color: var(--text-muted);
      transition: background 0.2s ease;
    }

    .accordion-header:hover {
      background: rgba(22, 32, 50, 0.9);
    }

    .reasoning-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
      margin-top: 14px;
    }

    .step-item {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 14px 16px;
      font-size: 13px;
    }

    .step-header {
      display: flex;
      justify-content: space-between;
      color: var(--primary);
      font-weight: 700;
      margin-bottom: 6px;
    }

    .step-thought {
      color: #e2e8f0;
      margin-bottom: 6px;
    }

    .step-obs {
      font-size: 12px;
      color: var(--text-muted);
      background: rgba(0, 0, 0, 0.2);
      padding: 6px 10px;
      border-radius: 4px;
      font-family: monospace;
    }

    /* Trade-offs Section */
    .tradeoffs-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 20px;
    }

    .tradeoffs-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .tradeoffs-list li {
      position: relative;
      padding-left: 24px;
      font-size: 13px;
      color: #cbd5e1;
    }

    .tradeoffs-list li::before {
      content: "✦";
      position: absolute;
      left: 4px;
      top: 0px;
      color: var(--primary);
      font-size: 14px;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-logo">IC</div>
      <div class="brand-text">
        <h1>Interior Company × Blocks</h1>
        <p>Autonomous AI Interior Design Agent • ReAct Reasoning & BOQ Engine</p>
      </div>
    </div>
    <div class="header-badges">
      <span class="badge badge-primary">Catalog v1.0 (72 SKUs)</span>
      <span class="badge badge-success">P0 Guardrails Active</span>
    </div>
  </header>

  <main>
    <!-- Left Configuration Sidebar -->
    <div class="sidebar">
      <div class="card">
        <div class="card-title">Select Preset Brief</div>
        <div class="form-group">
          <label>Golden Test Set & DB Briefs</label>
          <select id="preset-select" onchange="loadPreset()">
            <option value="">-- Choose a Brief --</option>
            <optgroup label="Database Golden Set (BR-01 to BR-14)">
              <option value="BR-01" selected>BR-01: Scandi Living Sanctuary (4.8x3.6m)</option>
              <option value="BR-02">BR-02: Mid-Century Rented (Freestanding Only)</option>
              <option value="BR-03">BR-03: Minimalist Master Bedroom</option>
              <option value="BR-04">BR-04: Contemporary 6-Seater Dining</option>
              <option value="BR-05">BR-05: Bohemian Living (Strictly NO TV)</option>
              <option value="BR-06">BR-06: Budget Deficit Stress (₹45,000 Cap)</option>
              <option value="BR-07">BR-07: Civil Structural Safety (Demolition Query)</option>
              <option value="BR-08">BR-08: Designer Brand Sourcing (Togo/Noguchi)</option>
              <option value="BR-09">BR-09: Studio Overcrowding (8-Seater Table)</option>
              <option value="BR-10">BR-10: Commercial SLA & Discount Lock Trap</option>
              <option value="BR-11">BR-11: Industrial Ergonomic WFH Study</option>
              <option value="BR-12">BR-12: Kids Room (Durable & Safe)</option>
              <option value="BR-13">BR-13: Grand Traditional Rosewood Dining</option>
              <option value="BR-14">BR-14: Luxury Statement Living (Italian Boucle)</option>
            </optgroup>
            <optgroup label="Synthetic Edge & Guardrail Cases">
              <option value="SYN-01">SYN-01: Null Price Trapping Test</option>
              <option value="SYN-02">SYN-02: Immediate Delivery (In-Stock Only)</option>
              <option value="SYN-03">SYN-03: Industrial Coastal Style Harmony</option>
              <option value="SYN-04">SYN-04: Null Dimensions Median Imputation</option>
              <option value="SYN-05">SYN-05: Zero Budget Edge Case</option>
              <option value="SYN-06">SYN-06: Micro-Room (2.0x2.0m) Overcrowding</option>
              <option value="SYN-07">SYN-07: Plumbing Slab Relocation Refusal</option>
              <option value="SYN-08">SYN-08: 220V Electrical Splicing Refusal</option>
              <option value="SYN-09">SYN-09: 30% Commercial Discount Refusal</option>
              <option value="SYN-10">SYN-10: IKEA Billy & Poang Substitution</option>
              <option value="SYN-11">SYN-11: Negative Budget Refusal</option>
            </optgroup>
          </select>
        </div>

        <div class="form-group">
          <label>Room Type</label>
          <select id="input-room-type">
            <option value="Living Room">Living Room</option>
            <option value="Bedroom">Bedroom</option>
            <option value="Dining">Dining</option>
            <option value="Study">Study</option>
            <option value="Kids">Kids Room</option>
          </select>
        </div>

        <div class="form-group">
          <label>Dimensions (Length x Width x Height cm)</label>
          <div class="dim-grid">
            <input type="number" id="input-length" placeholder="L cm" value="480">
            <input type="number" id="input-width" placeholder="W cm" value="360">
            <input type="number" id="input-height" placeholder="H cm" value="300">
          </div>
        </div>

        <div class="form-group">
          <label>Budget (INR)</label>
          <input type="number" id="input-budget" value="250000">
        </div>

        <div class="form-group">
          <label>Style Preference</label>
          <select id="input-style">
            <option value="Scandinavian">Scandinavian</option>
            <option value="Mid-Century">Mid-Century</option>
            <option value="Minimalist">Minimalist</option>
            <option value="Contemporary">Contemporary</option>
            <option value="Bohemian">Bohemian</option>
            <option value="Industrial">Industrial</option>
            <option value="Traditional">Traditional</option>
            <option value="Coastal">Coastal</option>
          </select>
        </div>

        <div class="form-group">
          <label>Must Haves</label>
          <input type="text" id="input-must-haves" value="3-seater sofa, coffee table, TV unit, rug, lighting">
        </div>

        <div class="form-group">
          <label>Constraints & Customer Notes</label>
          <textarea id="input-notes" rows="3">South-facing, lots of natural light; couple, no kids yet.</textarea>
        </div>

        <button class="btn-run" onclick="generatePlan()">
          <span>⚡</span> Run ReAct Agent
        </button>
      </div>
    </div>

    <!-- Right Output Workspace -->
    <div class="workspace" id="output-workspace">
      <!-- Status Banner -->
      <div id="status-card" class="status-banner status-success">
        <div class="status-left">
          <span id="status-icon">✅</span>
          <span id="status-text">Brief Solved: All Spatial and Financial Bounds Verified</span>
        </div>
        <div class="status-pill" id="status-code">STATUS: SUCCESS</div>
      </div>

      <!-- Key Metrics -->
      <div class="metrics-grid">
        <div class="metric-box">
          <div class="metric-label">Allocated Budget</div>
          <div class="metric-value" id="val-budget">₹2,50,000</div>
          <div class="metric-sub">Customer Ceiling</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">Total Spent</div>
          <div class="metric-value" id="val-spent">₹1,28,900</div>
          <div class="metric-sub" id="val-utilization">51.6% Utilization</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">Room Area</div>
          <div class="metric-value" id="val-area">17.28 sqm</div>
          <div class="metric-sub" id="val-footprint">Footprint: 3.58 sqm</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">Floor Occupancy</div>
          <div class="metric-value" id="val-occupancy">20.7%</div>
          <div class="metric-sub" id="val-circulation" style="color: #34d399;">Safe (<35% Limit)</div>
        </div>
      </div>

      <!-- Design Concept Card -->
      <div class="concept-hero">
        <div class="concept-theme" id="concept-theme">Calm Scandinavian Living Sanctuary</div>
        <div class="concept-palette" id="concept-palette">Light blonde oak, oatmeal woven fabric, matte white, textured boucle wool</div>
        <div class="concept-rationale" id="concept-rationale">
          Design tailored for Living Room (17.28 sqm). Selected balanced proportions to maintain an open 20.7% floor occupancy, preserving generous >80cm walkways. Harmonized material palette with natural lighting orientation.
        </div>
      </div>

      <!-- Itemized Bill of Quantities (BOQ) -->
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Item SKU</th>
              <th>Category</th>
              <th>Product Name</th>
              <th>Dimensions</th>
              <th>Finish</th>
              <th>Price (INR)</th>
              <th>Availability</th>
              <th>Lead Time</th>
            </tr>
          </thead>
          <tbody id="boq-tbody">
            <!-- Filled via JS -->
          </tbody>
        </table>
      </div>

      <!-- Trade-offs Disclosures -->
      <div class="tradeoffs-card">
        <div class="card-title">Transparent Trade-Offs & Disclosures</div>
        <ul class="tradeoffs-list" id="tradeoffs-list">
          <li>Prioritized foundational seating and circulation clearance over non-essential accessories.</li>
        </ul>
      </div>

      <!-- ReAct Audit Trail Accordion -->
      <div class="accordion-header" onclick="toggleAccordion()">
        <span>🤖 Agent ReAct Reasoning Loop (Thoughts, Actions & Observations)</span>
        <span id="accordion-icon">▼</span>
      </div>
      <div class="reasoning-list" id="reasoning-container" style="display: none;">
        <!-- Filled via JS -->
      </div>
    </div>
  </main>

  <script>
    let currentBriefs = {};

    async function init() {
      try {
        const res = await fetch('/api/briefs');
        currentBriefs = await res.json();
      } catch (err) {
        console.error('Failed to load preset briefs:', err);
      }
      generatePlan();
    }

    function loadPreset() {
      const select = document.getElementById('preset-select');
      const val = select.value;
      if (!val || !currentBriefs[val]) return;

      const tc = currentBriefs[val];
      const inp = tc.input || tc;

      document.getElementById('input-room-type').value = inp.room_type || 'Living Room';
      const dims = inp.dimensions || [400, 350, 280];
      document.getElementById('input-length').value = dims[0] || 400;
      document.getElementById('input-width').value = dims[1] || 350;
      document.getElementById('input-height').value = dims[2] || 280;
      document.getElementById('input-budget').value = inp.budget_inr !== undefined ? inp.budget_inr : 200000;
      document.getElementById('input-style').value = inp.style || inp.style_preference || 'Contemporary';
      document.getElementById('input-must-haves').value = inp.must_haves || '';
      document.getElementById('input-notes').value = inp.notes || inp.customer_note || '';

      generatePlan();
    }

    async function generatePlan() {
      const payload = {
        brief_id: document.getElementById('preset-select').value || 'CUSTOM-01',
        room_type: document.getElementById('input-room-type').value,
        dimensions: [
          parseInt(document.getElementById('input-length').value) || 400,
          parseInt(document.getElementById('input-width').value) || 350,
          parseInt(document.getElementById('input-height').value) || 280
        ],
        budget_inr: parseInt(document.getElementById('input-budget').value) || 0,
        style: document.getElementById('input-style').value,
        must_haves: document.getElementById('input-must-haves').value,
        notes: document.getElementById('input-notes').value
      };

      try {
        const res = await fetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        renderResult(data);
      } catch (err) {
        console.error('Error generating plan:', err);
      }
    }

    function renderResult(data) {
      // 1. Status Banner
      const statusCard = document.getElementById('status-card');
      const statusText = document.getElementById('status-text');
      const statusCode = document.getElementById('status-code');
      const statusIcon = document.getElementById('status-icon');

      statusCode.innerText = 'STATUS: ' + (data.status || 'SUCCESS');

      if (data.status === 'SUCCESS') {
        statusCard.className = 'status-banner status-success';
        statusIcon.innerText = '✅';
        statusText.innerText = 'Design Plan Approved: Within Budget & Circulation Safe';
      } else if (data.status === 'BUDGET_DEFICIT_FLAGGED') {
        statusCard.className = 'status-banner status-warning';
        statusIcon.innerText = '⚠️';
        statusText.innerText = 'Budget Deficit Flagged: Core Seating Preserved, Optional Items Deferred';
      } else if (data.status === 'CATALOG_SUBSTITUTION') {
        statusCard.className = 'status-banner status-substitution';
        statusIcon.innerText = '🔄';
        statusText.innerText = 'External Brands Replaced with Verified In-Catalog Equivalents';
      } else {
        statusCard.className = 'status-banner status-refusal';
        statusIcon.innerText = '🛑';
        statusText.innerText = data.refusal_reason || 'Operational Guardrail Refusal: Scope Limitation Intercepted';
      }

      // 2. Metrics
      const fin = data.financial_summary || {};
      const spat = data.spatial_fit_summary || {};

      document.getElementById('val-budget').innerText = '₹' + (fin.budget_allocated_inr || 0).toLocaleString();
      document.getElementById('val-spent').innerText = '₹' + (fin.total_spent_inr || 0).toLocaleString();
      document.getElementById('val-utilization').innerText = (fin.budget_utilization_percentage || 0) + '% Utilization';

      document.getElementById('val-area').innerText = (spat.room_area_sqm || 0) + ' sqm';
      document.getElementById('val-footprint').innerText = 'Footprint: ' + (spat.furniture_footprint_sqm || 0) + ' sqm';
      document.getElementById('val-occupancy').innerText = spat.occupancy_percentage || '0%';

      const circElem = document.getElementById('val-circulation');
      if (spat.circulation_viable) {
        circElem.innerText = 'Safe (<35% Limit)';
        circElem.style.color = '#34d399';
      } else {
        circElem.innerText = 'Blocked (>35% Limit)';
        circElem.style.color = '#fb7185';
      }

      // 3. Concept
      const conc = data.design_concept || {};
      document.getElementById('concept-theme').innerText = conc.theme || 'Interior Design Brief';
      document.getElementById('concept-palette').innerText = conc.palette_and_materials || 'Curated Material Palette';
      document.getElementById('concept-rationale').innerText = conc.rationale || 'N/A';

      // 4. BOQ Table
      const tbody = document.getElementById('boq-tbody');
      tbody.innerHTML = '';
      const boq = data.boq || [];

      if (boq.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 32px;">No items in BOQ due to operational refusal or budget constraint.</td></tr>';
      } else {
        boq.forEach(item => {
          const tr = document.createElement('tr');
          const priceDisplay = item.price_inr ? '₹' + item.price_inr.toLocaleString() : '<span style="color: #fbbf24;">Quote Req.</span>';
          const stockClass = item.in_stock ? 'stock-in' : 'stock-out';
          const stockLabel = item.in_stock ? 'In Stock' : 'Pre-order';

          tr.innerHTML = `
            <td><span class="sku-tag">${item.item_id}</span></td>
            <td>${item.category}</td>
            <td style="font-weight: 600;">${item.name}</td>
            <td style="color: var(--text-dim); font-size: 12px;">${item.dimensions}</td>
            <td style="color: var(--text-muted);">${item.finish}</td>
            <td style="font-weight: 700;">${priceDisplay}</td>
            <td><span class="stock-badge ${stockClass}">${stockLabel}</span></td>
            <td style="color: var(--text-muted);">${item.lead_time_days} days</td>
          `;
          tbody.appendChild(tr);
        });
      }

      // 5. Trade-offs
      const toList = document.getElementById('tradeoffs-list');
      toList.innerHTML = '';
      (data.trade_offs_and_omissions || []).forEach(t => {
        const li = document.createElement('li');
        li.innerText = t;
        toList.appendChild(li);
      });

      // 6. Reasoning Accordion
      const rContainer = document.getElementById('reasoning-container');
      rContainer.innerHTML = '';
      (data.reasoning_steps || []).forEach(step => {
        const div = document.createElement('div');
        div.className = 'step-item';
        div.innerHTML = `
          <div class="step-header">
            <span>Step ${step.step}: Action ➔ ${step.action}</span>
          </div>
          <div class="step-thought">${step.thought}</div>
          <div class="step-obs">Observation: ${step.observation}</div>
        `;
        rContainer.appendChild(div);
      });
    }

    function toggleAccordion() {
      const container = document.getElementById('reasoning-container');
      const icon = document.getElementById('accordion-icon');
      if (container.style.display === 'none') {
        container.style.display = 'flex';
        icon.innerText = '▲';
      } else {
        container.style.display = 'none';
        icon.innerText = '▼';
      }
    }

    window.onload = init;
  </script>
</body>
</html>
"""


class AgentRequestHandler(http.server.SimpleHTTPRequestHandler):
    agent = InteriorDesignAgent()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        elif parsed.path == "/api/briefs":
            golden_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_test_cases.json")
            briefs_map = {}
            if os.path.exists(golden_path):
                with open(golden_path, "r", encoding="utf-8") as f:
                    cases = json.load(f)
                    for c in cases:
                        b_id = c.get("brief_id") or c.get("test_id")
                        briefs_map[b_id] = c

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(briefs_map).encode("utf-8"))
            return

        elif parsed.path == "/api/catalog":
            items = tools.get_all_catalog_items()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(items).encode("utf-8"))
            return

        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/generate":
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length)
            try:
                brief_data = json.loads(post_body.decode("utf-8"))
                result = self.agent.run(brief_data)

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(result, indent=2).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self.send_error(404, "Endpoint not found")


def run_cli_brief(brief_id_or_file: str) -> None:
    agent = InteriorDesignAgent()
    golden_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_test_cases.json")
    target_brief = None

    if os.path.exists(golden_path):
        with open(golden_path, "r", encoding="utf-8") as f:
            cases = json.load(f)
            for c in cases:
                if c.get("brief_id") == brief_id_or_file or c.get("test_id") == brief_id_or_file:
                    target_brief = c
                    break

    if not target_brief:
        target_brief = {
            "brief_id": brief_id_or_file,
            "room_type": "Living Room",
            "dimensions": [480, 360, 300],
            "budget_inr": 250000,
            "style": "Scandinavian",
            "must_haves": "3-seater sofa, coffee table, TV unit, rug, lighting",
            "notes": f"Ad-hoc execution for {brief_id_or_file}"
        }

    print("\n" + "=" * 80)
    print(f"🛋️  RUNNING AI INTERIOR DESIGN AGENT: BRIEF '{brief_id_or_file}'")
    print("=" * 80)

    inp = target_brief.get("input", target_brief)
    dims = inp.get("dimensions", [400, 350, 280])
    print(f"Room: {inp.get('room_type')} | Style: {inp.get('style')} | Dimensions: {dims[0]}x{dims[1]}x{dims[2]}cm")
    print(f"Budget: ₹{inp.get('budget_inr', 0):,} | Must Haves: {inp.get('must_haves')}")
    print(f"Notes: {inp.get('notes')}")
    print("-" * 80)

    result = agent.run(target_brief)

    print(f"\nSTATUS: {result.get('status')}")
    concept = result.get("design_concept", {})
    print(f"THEME: {concept.get('theme')}")
    print(f"PALETTE: {concept.get('palette_and_materials')}")
    print(f"RATIONALE: {concept.get('rationale')}\n")

    fin = result.get("financial_summary", {})
    spat = result.get("spatial_fit_summary", {})
    print(f"FINANCIALS: Spent ₹{fin.get('total_spent_inr', 0):,} / ₹{fin.get('budget_allocated_inr', 0):,} ({fin.get('budget_utilization_percentage')}%) | Remaining: ₹{fin.get('remaining_budget_inr', 0):,}")
    print(f"SPATIAL: Room Area: {spat.get('room_area_sqm')} sqm | Furniture Footprint: {spat.get('furniture_footprint_sqm')} sqm | Occupancy: {spat.get('occupancy_percentage')} | Viable: {spat.get('circulation_viable')}")

    print("\nITEMIZED BILL OF QUANTITIES (BOQ):")
    print(f"{'SKU':<10} | {'Category':<14} | {'Product Name':<30} | {'Price (INR)':<12} | {'Lead Time'}")
    print("-" * 80)
    boq = result.get("boq", [])
    if not boq:
        print("  [No items selected - Operational Refusal / Budget Deficit]")
    else:
        for item in boq:
            price_str = f"₹{item['price_inr']:,}" if item["price_inr"] else "Quote Req."
            print(f"{item['item_id']:<10} | {item['category']:<14} | {item['name']:<30} | {price_str:<12} | {item['lead_time_days']} days")

    print("\nTRANSPARENT TRADE-OFFS & OMISSIONS:")
    for to in result.get("trade_offs_and_omissions", []):
        print(f"  ✦ {to}")

    print("\nREASONING STEPS & AUDIT TRAIL:")
    for s in result.get("reasoning_steps", []):
        print(f"  Step {s['step']} [Action: {s['action']}]: {s['thought'][:75]}...")
        print(f"    ↳ Observation: {s['observation']}")

    print("=" * 80 + "\n")


def start_server(port: int = 8080) -> None:
    server_address = ("", port)
    httpd = socketserver.TCPServer(server_address, AgentRequestHandler)
    print("\n" + "=" * 80)
    print(f"🌐 INTERIOR COMPANY x BLOCKS — AI AGENT SERVER RUNNING")
    print("=" * 80)
    print(f"  ➜ Local Web Demo: http://localhost:{port}")
    print(f"  ➜ Catalog Explorer: http://localhost:{port}/api/catalog")
    print(f"  ➜ Briefs API: http://localhost:{port}/api/briefs")
    print("  Press Ctrl+C to stop the server.")
    print("=" * 80 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous AI Interior Design Agent MVP")
    parser.add_argument("--brief", type=str, help="Run CLI evaluation on a specific Brief ID (e.g. BR-01, BR-07)")
    parser.add_argument("--eval", action="store_true", help="Run the full 25-case golden evaluation harness")
    parser.add_argument("--serve", action="store_true", help="Start the interactive web server")
    parser.add_argument("--port", type=int, default=8080, help="Port for web server (default: 8080)")

    args = parser.parse_args()

    if args.eval:
        import run_evals
        run_evals.run_all_evaluations()
    elif args.brief:
        run_cli_brief(args.brief)
    elif args.serve or len(sys.argv) == 1:
        start_server(args.port)
    else:
        parser.print_help()
