"""
run_app.py - Runnable MVP Application (Interactive Web UI & CLI)
Autonomous AI Interior Design Agent for Interior Company x Blocks.
Features:
  1. Siya: User-driven conversational consultant with real-time SQLite persistence.
  2. Direct BOQ Generator: Enterprise parametric brief evaluation harness.
  3. Real-time catalog search, budget calculator, and layout fit checker.

Usage:
  Interactive Web UI:
    python run_app.py --serve
    python run_app.py --port 8080

  CLI Mode:
    python run_app.py --brief BR-01
    python run_app.py --brief BR-07
    python run_app.py --eval
"""

import argparse
import http.server
import json
import os
import socketserver
import sys
import urllib.parse
from typing import Dict, Any, Optional

import db
import tools
from agent import InteriorDesignAgent
from agents.conversation_agent import ConversationAgent

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
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-base: #0a0e17;
      --bg-surface: #111827;
      --bg-card: #162032;
      --bg-card-hover: #1c2940;
      --bg-glass: rgba(22, 32, 50, 0.75);
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-accent: rgba(99, 102, 241, 0.35);
      --primary: #6366f1;
      --primary-glow: rgba(99, 102, 241, 0.3);
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
      background: rgba(10, 14, 23, 0.88);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border-subtle);
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 14px 28px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }

    .brand-logo {
      width: 42px;
      height: 42px;
      background: linear-gradient(135deg, var(--primary), var(--accent-sky));
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      font-weight: 800;
      color: #fff;
      box-shadow: 0 0 16px var(--primary-glow);
    }

    .brand-text h1 {
      font-family: 'Space Grotesk', sans-serif;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.5px;
      color: var(--text-main);
    }

    .brand-text p {
      font-size: 12px;
      color: var(--text-muted);
    }

    /* Navigation Mode Tabs */
    .nav-tabs {
      display: flex;
      background: rgba(17, 24, 39, 0.9);
      padding: 4px;
      border-radius: 12px;
      border: 1px solid var(--border-subtle);
      gap: 4px;
    }

    .nav-tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 13px;
      font-weight: 600;
      padding: 8px 18px;
      border-radius: 9px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
    }

    .nav-tab-btn:hover {
      color: var(--text-main);
    }

    .nav-tab-btn.active {
      background: var(--primary);
      color: #fff;
      box-shadow: 0 2px 10px var(--primary-glow);
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
      display: inline-flex;
      align-items: center;
      gap: 5px;
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

    /* Tab View Containers */
    .tab-view {
      display: none;
      flex: 1;
      width: 100%;
      max-width: 1540px;
      margin: 0 auto;
      padding: 24px 28px;
    }

    .tab-view.active {
      display: grid;
    }

    /* ========================================================= */
    /* CHAT VIEW (SIYA INTERACTIVE CONSULTANT)                   */
    /* ========================================================= */
    #view-chat {
      grid-template-columns: 360px 1fr;
      gap: 24px;
      height: calc(100vh - 84px);
    }

    @media (max-width: 1024px) {
      #view-chat {
        grid-template-columns: 1fr;
        height: auto;
      }
    }

    .chat-sidebar {
      display: flex;
      flex-direction: column;
      gap: 16px;
      overflow-y: auto;
    }

    .card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 20px;
      box-shadow: var(--shadow-sm);
    }

    .card-title {
      font-family: 'Space Grotesk', sans-serif;
      font-size: 14px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .spec-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      font-size: 13px;
    }

    .spec-item:last-child {
      border-bottom: none;
    }

    .spec-label {
      color: var(--text-muted);
    }

    .spec-value {
      font-weight: 600;
      color: var(--text-main);
      text-align: right;
    }

    .spec-pill {
      background: rgba(99, 102, 241, 0.18);
      color: #a5b4fc;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
    }

    .rule-box {
      font-size: 12px;
      color: var(--text-muted);
      line-height: 1.5;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .rule-item {
      display: flex;
      align-items: flex-start;
      gap: 8px;
    }

    /* Main Chat Panel */
    .chat-panel {
      display: flex;
      flex-direction: column;
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      overflow: hidden;
      box-shadow: var(--shadow-lg);
      height: 100%;
    }

    .chat-header {
      padding: 16px 22px;
      background: rgba(17, 24, 39, 0.85);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .chat-agent-info {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .chat-avatar-lg {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: linear-gradient(135deg, #a855f7, #6366f1);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      box-shadow: 0 0 12px rgba(168, 85, 247, 0.35);
    }

    .chat-name {
      font-weight: 700;
      font-size: 15px;
      color: var(--text-main);
    }

    .chat-status {
      font-size: 12px;
      color: var(--accent-emerald);
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .pulse-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background-color: var(--accent-emerald);
      box-shadow: 0 0 8px var(--accent-emerald);
    }

    .chat-actions {
      display: flex;
      gap: 8px;
    }

    .btn-secondary {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid var(--border-subtle);
      color: var(--text-muted);
      font-size: 12px;
      font-weight: 600;
      padding: 6px 12px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      transition: all 0.2s;
    }

    .btn-secondary:hover {
      background: rgba(255, 255, 255, 0.12);
      color: var(--text-main);
    }

    /* Message History Stream */
    .chat-history {
      flex: 1;
      padding: 24px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 18px;
      scroll-behavior: smooth;
    }

    .message-row {
      display: flex;
      gap: 12px;
      max-width: 82%;
    }

    .message-row.bot {
      align-self: flex-start;
    }

    .message-row.user {
      align-self: flex-end;
      flex-direction: row-reverse;
    }

    .msg-avatar {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      flex-shrink: 0;
    }

    .bot .msg-avatar {
      background: linear-gradient(135deg, #a855f7, #6366f1);
      box-shadow: 0 0 8px rgba(168, 85, 247, 0.3);
    }

    .user .msg-avatar {
      background: linear-gradient(135deg, #3b82f6, #0ea5e9);
    }

    .msg-bubble {
      padding: 14px 18px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.55;
      position: relative;
      word-break: break-word;
      white-space: pre-wrap;
    }

    .bot .msg-bubble {
      background: #1e293b;
      color: #f1f5f9;
      border-top-left-radius: 4px;
      border: 1px solid rgba(255, 255, 255, 0.06);
    }

    .user .msg-bubble {
      background: linear-gradient(135deg, #4f46e5, #6366f1);
      color: #ffffff;
      border-top-right-radius: 4px;
      box-shadow: 0 4px 14px rgba(79, 70, 229, 0.3);
    }

    /* Embedded Plan Card in Chat */
    .embedded-plan-card {
      margin-top: 14px;
      background: rgba(10, 14, 23, 0.6);
      border: 1px solid rgba(99, 102, 241, 0.35);
      border-radius: 12px;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .plan-header-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .plan-title {
      font-family: 'Space Grotesk', sans-serif;
      font-weight: 700;
      color: #a5b4fc;
      font-size: 14px;
    }

    .plan-stats-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      background: rgba(255, 255, 255, 0.03);
      padding: 10px;
      border-radius: 8px;
    }

    .plan-stat-item {
      display: flex;
      flex-direction: column;
    }

    .plan-stat-label {
      font-size: 11px;
      color: var(--text-muted);
    }

    .plan-stat-val {
      font-weight: 700;
      font-size: 13px;
      color: #f8fafc;
    }

    .plan-actions {
      display: flex;
      gap: 8px;
      margin-top: 4px;
    }

    .btn-plan-action {
      flex: 1;
      padding: 8px 12px;
      font-size: 12px;
      font-weight: 600;
      border-radius: 6px;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s;
    }

    .btn-plan-primary {
      background: var(--primary);
      color: white;
    }

    .btn-plan-primary:hover {
      background: var(--primary-hover);
    }

    /* Quick Reply Suggestion Chips */
    .chat-chips-container {
      padding: 10px 22px;
      background: rgba(17, 24, 39, 0.7);
      border-top: 1px solid var(--border-subtle);
      display: flex;
      gap: 8px;
      overflow-x: auto;
      white-space: nowrap;
    }

    .suggestion-chip {
      background: rgba(99, 102, 241, 0.12);
      border: 1px solid rgba(99, 102, 241, 0.3);
      color: #c7d2fe;
      font-size: 12px;
      font-weight: 600;
      padding: 6px 14px;
      border-radius: 9999px;
      cursor: pointer;
      transition: all 0.2s ease;
      flex-shrink: 0;
    }

    .suggestion-chip:hover {
      background: var(--primary);
      color: #fff;
      transform: translateY(-1px);
      box-shadow: 0 4px 10px var(--primary-glow);
    }

    /* Chat Input Form */
    .chat-input-bar {
      padding: 16px 22px;
      background: rgba(10, 14, 23, 0.95);
      border-top: 1px solid var(--border-subtle);
      display: flex;
      gap: 12px;
      align-items: center;
    }

    .chat-input-field {
      flex: 1;
      background: #1e293b;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 10px;
      padding: 12px 16px;
      color: #fff;
      font-family: inherit;
      font-size: 14px;
      outline: none;
      transition: border 0.2s;
    }

    .chat-input-field:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
    }

    .btn-send {
      background: var(--primary);
      border: none;
      color: white;
      width: 44px;
      height: 44px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 16px;
      transition: all 0.2s;
      flex-shrink: 0;
    }

    .btn-send:hover {
      background: var(--primary-hover);
      transform: scale(1.04);
    }

    .btn-send:disabled {
      background: var(--text-dim);
      cursor: not-allowed;
      transform: none;
    }

    /* ========================================================= */
    /* DIRECT BOQ GENERATOR VIEW (CLASSIC WORKBENCH)             */
    /* ========================================================= */
    #view-boq {
      grid-template-columns: 400px 1fr;
      gap: 28px;
    }

    @media (max-width: 1024px) {
      #view-boq {
        grid-template-columns: 1fr;
      }
    }

    .form-group {
      margin-bottom: 16px;
    }

    .form-label {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      margin-bottom: 6px;
      display: block;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .form-control {
      width: 100%;
      background: rgba(10, 14, 23, 0.6);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 10px 14px;
      color: var(--text-main);
      font-family: inherit;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }

    .form-control:focus {
      border-color: var(--primary);
    }

    .dim-inputs {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 8px;
    }

    .btn-primary {
      width: 100%;
      background: var(--primary);
      border: none;
      color: #fff;
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 14px;
      font-weight: 700;
      padding: 12px 20px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: all 0.2s;
      box-shadow: 0 4px 14px var(--primary-glow);
    }

    .btn-primary:hover {
      background: var(--primary-hover);
      box-shadow: 0 6px 20px var(--primary-glow);
    }

    /* Output Section */
    .output-area {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    /* Status Banner */
    .status-banner {
      border-radius: var(--radius-md);
      padding: 16px 20px;
      display: flex;
      align-items: center;
      gap: 16px;
      box-shadow: var(--shadow-sm);
      border: 1px solid transparent;
    }

    .status-success {
      background: rgba(16, 185, 129, 0.1);
      border-color: rgba(16, 185, 129, 0.3);
      color: #34d399;
    }

    .status-warning {
      background: rgba(245, 158, 11, 0.1);
      border-color: rgba(245, 158, 11, 0.3);
      color: #fbbf24;
    }

    .status-refusal {
      background: rgba(244, 63, 94, 0.1);
      border-color: rgba(244, 63, 94, 0.3);
      color: #fb7185;
    }

    .status-substitution {
      background: rgba(14, 165, 233, 0.1);
      border-color: rgba(14, 165, 233, 0.3);
      color: #38bdf8;
    }

    .status-icon {
      font-size: 24px;
    }

    .status-meta h4 {
      font-size: 15px;
      font-weight: 700;
      color: inherit;
    }

    .status-meta p {
      font-size: 13px;
      color: var(--text-muted);
    }

    /* Metrics Grid */
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

    .metric-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .metric-label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
    }

    .metric-value {
      font-family: 'Space Grotesk', sans-serif;
      font-size: 20px;
      font-weight: 700;
      color: var(--text-main);
    }

    .metric-sub {
      font-size: 11px;
      color: var(--text-dim);
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
      text-align: left;
      font-size: 13px;
    }

    thead {
      background: rgba(10, 14, 23, 0.8);
      border-bottom: 1px solid var(--border-subtle);
    }

    th {
      padding: 12px 16px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
    }

    td {
      padding: 14px 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      color: var(--text-main);
    }

    tbody tr:hover {
      background: var(--bg-card-hover);
    }

    .sku-tag {
      font-family: monospace;
      font-size: 12px;
      background: rgba(255, 255, 255, 0.06);
      padding: 2px 6px;
      border-radius: 4px;
      color: var(--accent-sky);
    }

    .stock-badge {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 9999px;
      font-weight: 600;
    }

    .stock-in {
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
    }

    .stock-out {
      background: rgba(245, 158, 11, 0.15);
      color: #fbbf24;
    }

    /* Modal for BOQ Details */
    .modal-backdrop {
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.8);
      backdrop-filter: blur(8px);
      z-index: 1000;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }

    .modal-backdrop.show {
      display: flex;
    }

    .modal-window {
      background: var(--bg-surface);
      border: 1px solid var(--border-accent);
      border-radius: var(--radius-lg);
      width: 100%;
      max-width: 960px;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
      overflow: hidden;
    }

    .modal-header {
      padding: 18px 24px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .modal-title {
      font-family: 'Space Grotesk', sans-serif;
      font-size: 17px;
      font-weight: 700;
      color: #fff;
    }

    .modal-close {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 20px;
      cursor: pointer;
    }

    .modal-body {
      padding: 24px;
      overflow-y: auto;
    }

    /* ReAct Reasoning Accordion */
    .step-item {
      background: rgba(10, 14, 23, 0.5);
      border-left: 3px solid var(--primary);
      padding: 10px 14px;
      margin-bottom: 8px;
      border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    }

    .step-header {
      font-size: 12px;
      font-weight: 700;
      color: #818cf8;
      margin-bottom: 4px;
    }

    .step-thought {
      font-size: 13px;
      color: var(--text-main);
      margin-bottom: 4px;
    }

    .step-obs {
      font-size: 12px;
      color: var(--text-muted);
      font-family: monospace;
      background: rgba(0, 0, 0, 0.3);
      padding: 4px 8px;
      border-radius: 4px;
    }
  </style>
</head>
<body>

  <!-- Top Header Navigation -->
  <header>
    <div class="brand">
      <div class="brand-logo">IC</div>
      <div class="brand-text">
        <h1>Interior Company x Blocks</h1>
        <p>Autonomous AI Interior Design Consultant & BOQ Engine</p>
      </div>
    </div>

    <!-- Mode Selector Tabs -->
    <div class="nav-tabs">
      <button class="nav-tab-btn active" id="tab-btn-chat" onclick="switchTab('chat')">
        💬 Chat with Siya (Consultant)
      </button>
      <button class="nav-tab-btn" id="tab-btn-boq" onclick="switchTab('boq')">
        ⚡ Direct BOQ Generator
      </button>
    </div>

    <div class="header-badges">
      <span class="badge badge-primary">✨ Siya Online</span>
      <span class="badge badge-success">📦 38 Verified SKUs</span>
      <span class="badge badge-primary">📐 Circulation Limit (&lt;35%)</span>
    </div>
  </header>

  <!-- ======================================================= -->
  <!-- TAB 1: INTERACTIVE CHAT WITH SIYA                       -->
  <!-- ======================================================= -->
  <main id="view-chat" class="tab-view active">
    <!-- Left Chat Sidebar: Real-Time Session Status -->
    <div class="chat-sidebar">
      <div class="card">
        <div class="card-title">
          <span>Room Specifications</span>
          <span class="spec-pill" id="chat-stage-badge">GREETING</span>
        </div>
        <div class="spec-item">
          <span class="spec-label">Room Type</span>
          <span class="spec-value" id="spec-room-type">—</span>
        </div>
        <div class="spec-item">
          <span class="spec-label">Dimensions</span>
          <span class="spec-value" id="spec-dimensions">—</span>
        </div>
        <div class="spec-item">
          <span class="spec-label">Floor Area</span>
          <span class="spec-value" id="spec-area">—</span>
        </div>
        <div class="spec-item">
          <span class="spec-label">Budget</span>
          <span class="spec-value" id="spec-budget">—</span>
        </div>
        <div class="spec-item">
          <span class="spec-label">Design Style</span>
          <span class="spec-value" id="spec-style">—</span>
        </div>
        <div class="spec-item">
          <span class="spec-label">Must-Haves</span>
          <span class="spec-value" id="spec-must-haves" style="max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">—</span>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Guardrail Safety Matrix</div>
        <div class="rule-box">
          <div class="rule-item">
            <span>🛡️</span>
            <span><strong>Civil/Structural:</strong> Absolute refusal on load-bearing walls, plumbing, exterior facades.</span>
          </div>
          <div class="rule-item">
            <span>📐</span>
            <span><strong>Circulation Rule:</strong> Max 35% footprint occupancy (rugs & wall decor excluded).</span>
          </div>
          <div class="rule-item">
            <span>💰</span>
            <span><strong>Budget Cap:</strong> Transparent overage explanation & tier swaps.</span>
          </div>
          <div class="rule-item">
            <span>🔄</span>
            <span><strong>Catalog Fallbacks:</strong> Replaces missing brands with in-catalog verified items.</span>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Session Persistence</div>
        <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">
          All conversation turns, room briefs, and generated plans are synced to SQLite in real time.
        </p>
        <button class="btn-secondary" style="width: 100%;" onclick="resetChatSession()">
          🔄 Start New Consultation
        </button>
      </div>
    </div>

    <!-- Right Chat Main Container -->
    <div class="chat-panel">
      <!-- Chat Header -->
      <div class="chat-header">
        <div class="chat-agent-info">
          <div class="chat-avatar-lg">🛋️</div>
          <div>
            <div class="chat-name">Siya — Senior Interior Designer</div>
            <div class="chat-status">
              <span class="pulse-dot"></span>
              <span>Online • Catalog & Spatial Engine Active</span>
            </div>
          </div>
        </div>
        <div class="chat-actions">
          <button class="btn-secondary" onclick="viewSessionPlanModal()" id="btn-view-plan-top" style="display: none;">
            📋 View Full BOQ
          </button>
        </div>
      </div>

      <!-- Messages Stream -->
      <div class="chat-history" id="chat-history">
        <!-- Messages will be injected here dynamically -->
      </div>

      <!-- Quick Suggestion Chips -->
      <div class="chat-chips-container" id="chat-chips">
        <!-- Suggestions chips injected dynamically -->
      </div>

      <!-- Message Input Form -->
      <div class="chat-input-bar">
        <input 
          type="text" 
          id="chat-input" 
          class="chat-input-field" 
          placeholder="Reply to Siya (e.g., '14 * 12 feet', 'Scandinavian', 'make it cheaper')..."
          autocomplete="off"
        />
        <button class="btn-send" id="btn-chat-send" onclick="sendUserMessage()">
          ➤
        </button>
      </div>
    </div>
  </main>

  <!-- ======================================================= -->
  <!-- TAB 2: DIRECT BOQ GENERATOR (PARAMETRIC WORKBENCH)      -->
  <!-- ======================================================= -->
  <main id="view-boq" class="tab-view">
    <!-- Left Control Sidebar -->
    <div class="sidebar">
      <div class="card">
        <div class="card-title">1. Select Room Brief</div>
        <div class="form-group">
          <label class="form-label">Pre-configured Golden Briefs</label>
          <select class="form-control" id="brief-select" onchange="loadSelectedBrief()">
            <option value="">-- Choose a Brief (BR-01 to BR-25) --</option>
          </select>
        </div>
      </div>

      <div class="card">
        <div class="card-title">2. Space & Design Constraints</div>
        <div class="form-group">
          <label class="form-label">Room Type</label>
          <select class="form-control" id="param-room-type">
            <option value="Living Room">Living Room</option>
            <option value="Bedroom">Bedroom</option>
            <option value="Dining">Dining</option>
            <option value="Study">Study</option>
            <option value="Kids Room">Kids Room</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Dimensions (L × W × H in cm)</label>
          <div class="dim-inputs">
            <input type="number" class="form-control" id="param-l" placeholder="L (cm)" value="480">
            <input type="number" class="form-control" id="param-w" placeholder="W (cm)" value="360">
            <input type="number" class="form-control" id="param-h" placeholder="H (cm)" value="300">
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Budget (INR ₹)</label>
          <input type="number" class="form-control" id="param-budget" value="250000" step="10000">
        </div>

        <div class="form-group">
          <label class="form-label">Aesthetic Style</label>
          <select class="form-control" id="param-style">
            <option value="Scandinavian">Scandinavian</option>
            <option value="Mid-Century">Mid-Century</option>
            <option value="Contemporary">Contemporary</option>
            <option value="Bohemian">Bohemian</option>
            <option value="Minimalist">Minimalist</option>
            <option value="Industrial">Industrial</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Must-Haves & Required Items</label>
          <input type="text" class="form-control" id="param-must-haves" value="3-seater sofa, coffee table, TV unit, rug, lighting">
        </div>

        <div class="form-group">
          <label class="form-label">Custom Notes & Client Constraints</label>
          <textarea class="form-control" id="param-notes" rows="2" placeholder="e.g. Needs high durability, pet friendly..."></textarea>
        </div>

        <button class="btn-primary" id="btn-generate" onclick="generateDirectPlan()">
          ⚡ Run Autonomous Design Agent
        </button>
      </div>
    </div>

    <!-- Right Output Display -->
    <div class="output-area">
      <!-- Status Banner -->
      <div id="status-card" class="status-banner status-success">
        <div class="status-icon" id="status-icon">✨</div>
        <div class="status-meta">
          <h4 id="status-code">AGENT READY</h4>
          <p id="status-text">Select a brief or adjust parameters and run the autonomous agent.</p>
        </div>
      </div>

      <!-- Financial & Spatial KPI Cards -->
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-label">Allocated Budget</div>
          <div class="metric-value" id="val-budget">₹0</div>
          <div class="metric-sub" id="val-remaining">Remaining: ₹0</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Total Spend (BOQ)</div>
          <div class="metric-value" id="val-spent">₹0</div>
          <div class="metric-sub" id="val-utilization">0% Utilization</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Room Area</div>
          <div class="metric-value" id="val-area">0 sqm</div>
          <div class="metric-sub" id="val-footprint">Footprint: 0 sqm</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Circulation Viability</div>
          <div class="metric-value" id="val-circulation" style="color: #34d399;">Safe</div>
          <div class="metric-sub" id="val-occupancy">0% Occupancy (&lt;35%)</div>
        </div>
      </div>

      <!-- Design Concept Card -->
      <div class="card">
        <div class="card-title">Design Concept & Rationale</div>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <div><strong style="color: var(--primary);">Theme:</strong> <span id="concept-theme">—</span></div>
          <div><strong style="color: var(--accent-gold);">Palette & Materials:</strong> <span id="concept-palette">—</span></div>
          <p id="concept-rationale" style="color: var(--text-muted); font-size: 13px; line-height: 1.5; margin-top: 4px;">—</p>
        </div>
      </div>

      <!-- BOQ Table -->
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Category</th>
              <th>Product Name</th>
              <th>Dimensions (cm)</th>
              <th>Finish</th>
              <th>Price (INR)</th>
              <th>Stock</th>
              <th>Lead Time</th>
            </tr>
          </thead>
          <tbody id="boq-tbody">
            <tr>
              <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 32px;">
                No design plan generated yet. Run the agent above to view itemized BOQ.
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Trade-offs & Omissions -->
      <div class="card">
        <div class="card-title">Trade-offs & Omissions</div>
        <ul id="tradeoffs-list" style="padding-left: 20px; font-size: 13px; color: var(--text-muted); display: flex; flex-direction: column; gap: 6px;">
          <li>None recorded.</li>
        </ul>
      </div>

      <!-- Reasoning Steps Accordion -->
      <div class="card">
        <div class="card-title" style="cursor: pointer;" onclick="toggleAccordion()">
          <span>ReAct Reasoning Audit Trail</span>
          <span id="accordion-icon">▼</span>
        </div>
        <div id="reasoning-container" style="display: none; flex-direction: column; gap: 8px; margin-top: 10px;">
        </div>
      </div>
    </div>
  </main>

  <!-- ======================================================= -->
  <!-- MODAL: FULL BOQ INSPECTOR (CALLED FROM CHAT)            -->
  <!-- ======================================================= -->
  <div class="modal-backdrop" id="modal-boq-backdrop" onclick="closeModalIfBackdrop(event)">
    <div class="modal-window">
      <div class="modal-header">
        <div class="modal-title">📋 Itemized Bill of Quantities (BOQ)</div>
        <button class="modal-close" onclick="closeBoqModal()">✕</button>
      </div>
      <div class="modal-body">
        <div class="metrics-grid" style="margin-bottom: 20px;">
          <div class="metric-card">
            <div class="metric-label">Allocated Budget</div>
            <div class="metric-value" id="modal-val-budget">₹0</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Total Spent</div>
            <div class="metric-value" id="modal-val-spent">₹0</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Floor Footprint</div>
            <div class="metric-value" id="modal-val-footprint">0 sqm</div>
          </div>
          <div class="metric-card">
            <div class="metric-label">Circulation Status</div>
            <div class="metric-value" id="modal-val-circulation">Safe</div>
          </div>
        </div>

        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>SKU</th>
                <th>Category</th>
                <th>Product Name</th>
                <th>Dimensions</th>
                <th>Price (INR)</th>
                <th>Stock</th>
                <th>Lead Time</th>
              </tr>
            </thead>
            <tbody id="modal-boq-tbody">
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <script>
    // App State
    let currentSessionId = 'siya-' + Math.random().toString(36).substring(2, 9);
    let briefsData = {};
    let activePlanData = null;

    // Tab Switching
    function switchTab(tab) {
      document.querySelectorAll('.nav-tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-view').forEach(v => v.classList.remove('active'));

      if (tab === 'chat') {
        document.getElementById('tab-btn-chat').classList.add('active');
        document.getElementById('view-chat').classList.add('active');
      } else {
        document.getElementById('tab-btn-boq').classList.add('active');
        document.getElementById('view-boq').classList.add('active');
      }
    }

    // =========================================================
    // CHAT ENGINE JAVASCRIPT
    // =========================================================
    async function initChat() {
      // Send initial trigger to greet user
      await sendChatRequest('Hi');
    }

    async function sendUserMessage() {
      const input = document.getElementById('chat-input');
      const text = input.value.trim();
      if (!text) return;

      appendChatMessage('user', text);
      input.value = '';

      // Disable send button while awaiting response
      const sendBtn = document.getElementById('btn-chat-send');
      sendBtn.disabled = true;

      try {
        await sendChatRequest(text);
      } catch (err) {
        appendChatMessage('bot', '⚠️ Connection error. Please ensure server is running.');
      } finally {
        sendBtn.disabled = false;
        input.focus();
      }
    }

    async function sendChatRequest(message) {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: currentSessionId,
          message: message
        })
      });

      const data = await res.json();
      if (data.message) {
        appendChatMessage('bot', data.message, data.metadata);
      }

      // Update specs sidebar
      await refreshSessionSidebar();
    }

    function appendChatMessage(sender, text, metadata = null) {
      const container = document.getElementById('chat-history');
      const row = document.createElement('div');
      row.className = `message-row ${sender}`;

      const avatar = document.createElement('div');
      avatar.className = 'msg-avatar';
      avatar.innerText = sender === 'bot' ? '🛋️' : '👤';

      const bubble = document.createElement('div');
      bubble.className = 'msg-bubble';
      bubble.innerText = text;

      // Check if metadata contains a generated plan
      if (metadata && metadata.plan) {
        activePlanData = metadata.plan;
        const plan = metadata.plan;
        const fin = plan.financial_summary || {};
        const spat = plan.spatial_fit_summary || {};

        const planCard = document.createElement('div');
        planCard.className = 'embedded-plan-card';
        planCard.innerHTML = `
          <div class="plan-header-row">
            <span class="plan-title">🛋️ ${plan.design_concept ? plan.design_concept.theme : 'Design Plan Ready'}</span>
            <span class="spec-pill">${plan.status}</span>
          </div>
          <div class="plan-stats-grid">
            <div class="plan-stat-item">
              <span class="plan-stat-label">Total Spend</span>
              <span class="plan-stat-val">₹${(fin.total_spent_inr || 0).toLocaleString()}</span>
            </div>
            <div class="plan-stat-item">
              <span class="plan-stat-label">Floor Occupancy</span>
              <span class="plan-stat-val">${spat.occupancy_percentage || '0%'}</span>
            </div>
            <div class="plan-stat-item">
              <span class="plan-stat-label">Circulation</span>
              <span class="plan-stat-val" style="color: ${spat.circulation_viable ? '#34d399' : '#fb7185'};">
                ${spat.circulation_viable ? 'Safe (<35%)' : 'Blocked'}
              </span>
            </div>
          </div>
          <div class="plan-actions">
            <button class="btn-plan-action btn-plan-primary" onclick="viewSessionPlanModal()">
              📋 View Full Itemized BOQ
            </button>
          </div>
        `;
        bubble.appendChild(planCard);
        document.getElementById('btn-view-plan-top').style.display = 'block';
        
        // Also sync data into Tab 2 Direct BOQ table
        renderDirectPlanResults(plan);
      }

      row.appendChild(avatar);
      row.appendChild(bubble);
      container.appendChild(row);

      // Scroll to bottom
      container.scrollTop = container.scrollHeight;

      // Update suggestion chips
      const chipsContainer = document.getElementById('chat-chips');
      chipsContainer.innerHTML = '';
      if (metadata && metadata.chips && metadata.chips.length > 0) {
        metadata.chips.forEach(chipText => {
          const chip = document.createElement('button');
          chip.className = 'suggestion-chip';
          chip.innerText = chipText;
          chip.onclick = () => {
            document.getElementById('chat-input').value = chipText;
            sendUserMessage();
          };
          chipsContainer.appendChild(chip);
        });
      }
    }

    async function refreshSessionSidebar() {
      try {
        const res = await fetch(`/api/chat/session?session_id=${currentSessionId}`);
        const s = await res.json();
        if (!s) return;

        document.getElementById('chat-stage-badge').innerText = s.stage || 'GREETING';
        document.getElementById('spec-room-type').innerText = s.room_type || '—';

        if (s.length_cm && s.width_cm) {
          const h = s.height_cm || 280;
          document.getElementById('spec-dimensions').innerText = `${s.length_cm} × ${s.width_cm} × ${h} cm`;
          const area = ((s.length_cm * s.width_cm) / 10000).toFixed(1);
          document.getElementById('spec-area').innerText = `${area} sqm`;
        } else {
          document.getElementById('spec-dimensions').innerText = '—';
          document.getElementById('spec-area').innerText = '—';
        }

        document.getElementById('spec-budget').innerText = s.budget_max ? `₹${Number(s.budget_max).toLocaleString()}` : '—';
        document.getElementById('spec-style').innerText = s.style || '—';

        if (s.must_haves) {
          try {
            const mh = JSON.parse(s.must_haves);
            document.getElementById('spec-must-haves').innerText = Array.isArray(mh) ? mh.join(', ') : mh;
          } catch(e) {
            document.getElementById('spec-must-haves').innerText = s.must_haves || '—';
          }
        }
      } catch (err) {
        console.error('Error refreshing session:', err);
      }
    }

    function resetChatSession() {
      currentSessionId = 'siya-' + Math.random().toString(36).substring(2, 9);
      document.getElementById('chat-history').innerHTML = '';
      document.getElementById('chat-chips').innerHTML = '';
      document.getElementById('btn-view-plan-top').style.display = 'none';
      activePlanData = null;
      refreshSessionSidebar();
      initChat();
    }

    // Modal Operations
    function viewSessionPlanModal() {
      if (!activePlanData) return;
      const plan = activePlanData;
      const fin = plan.financial_summary || {};
      const spat = plan.spatial_fit_summary || {};

      document.getElementById('modal-val-budget').innerText = '₹' + (fin.budget_allocated_inr || 0).toLocaleString();
      document.getElementById('modal-val-spent').innerText = '₹' + (fin.total_spent_inr || 0).toLocaleString();
      document.getElementById('modal-val-footprint').innerText = (spat.furniture_footprint_sqm || 0) + ' sqm';
      document.getElementById('modal-val-circulation').innerText = spat.circulation_viable ? 'Safe (<35%)' : 'Blocked (>35%)';
      document.getElementById('modal-val-circulation').style.color = spat.circulation_viable ? '#34d399' : '#fb7185';

      const tbody = document.getElementById('modal-boq-tbody');
      tbody.innerHTML = '';

      const boq = plan.boq || [];
      if (boq.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 24px;">No items in BOQ.</td></tr>';
      } else {
        boq.forEach(item => {
          const tr = document.createElement('tr');
          const priceDisplay = item.price_inr ? '₹' + item.price_inr.toLocaleString() : 'Quote Req.';
          const stockClass = item.in_stock ? 'stock-in' : 'stock-out';
          const stockLabel = item.in_stock ? 'In Stock' : 'Pre-order';

          tr.innerHTML = `
            <td><span class="sku-tag">${item.item_id}</span></td>
            <td>${item.category}</td>
            <td style="font-weight: 600;">${item.name}</td>
            <td style="color: var(--text-dim); font-size: 12px;">${item.dimensions}</td>
            <td style="font-weight: 700;">${priceDisplay}</td>
            <td><span class="stock-badge ${stockClass}">${stockLabel}</span></td>
            <td style="color: var(--text-muted);">${item.lead_time_days} days</td>
          `;
          tbody.appendChild(tr);
        });
      }

      document.getElementById('modal-boq-backdrop').classList.add('show');
    }

    function closeBoqModal() {
      document.getElementById('modal-boq-backdrop').classList.remove('show');
    }

    function closeModalIfBackdrop(e) {
      if (e.target.id === 'modal-boq-backdrop') {
        closeBoqModal();
      }
    }

    // Input Enter Key handler
    document.addEventListener('DOMContentLoaded', () => {
      const input = document.getElementById('chat-input');
      if (input) {
        input.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') {
            sendUserMessage();
          }
        });
      }
    });

    // =========================================================
    // DIRECT BOQ GENERATOR JAVASCRIPT
    // =========================================================
    async function loadBriefs() {
      try {
        const res = await fetch('/api/briefs');
        briefsData = await res.json();
        const select = document.getElementById('brief-select');
        select.innerHTML = '<option value="">-- Choose a Brief (BR-01 to BR-25) --</option>';

        Object.keys(briefsData).sort().forEach(id => {
          const b = briefsData[id];
          const inp = b.input || b;
          const opt = document.createElement('option');
          opt.value = id;
          opt.innerText = `${id}: ${inp.room_type} (${inp.style || 'Flexible'}) - ₹${(inp.budget_inr || 0).toLocaleString()}`;
          select.appendChild(opt);
        });
      } catch (err) {
        console.error('Failed to load briefs:', err);
      }
    }

    function loadSelectedBrief() {
      const id = document.getElementById('brief-select').value;
      if (!id || !briefsData[id]) return;

      const raw = briefsData[id];
      const b = raw.input || raw;

      document.getElementById('param-room-type').value = b.room_type || 'Living Room';
      const dims = b.dimensions || [450, 360, 280];
      document.getElementById('param-l').value = dims[0] || 450;
      document.getElementById('param-w').value = dims[1] || 360;
      document.getElementById('param-h').value = dims[2] || 280;
      document.getElementById('param-budget').value = b.budget_inr || 250000;
      document.getElementById('param-style').value = b.style || 'Scandinavian';
      document.getElementById('param-must-haves').value = b.must_haves || '';
      document.getElementById('param-notes').value = b.notes || '';
    }

    async function generateDirectPlan() {
      const btn = document.getElementById('btn-generate');
      btn.innerText = '⚙️ Designing Space & Validating Guardrails...';
      btn.disabled = true;

      const payload = {
        brief_id: document.getElementById('brief-select').value || 'CUSTOM',
        room_type: document.getElementById('param-room-type').value,
        dimensions: [
          parseInt(document.getElementById('param-l').value) || 450,
          parseInt(document.getElementById('param-w').value) || 360,
          parseInt(document.getElementById('param-h').value) || 280
        ],
        budget_inr: parseInt(document.getElementById('param-budget').value) || 250000,
        style: document.getElementById('param-style').value,
        must_haves: document.getElementById('param-must-haves').value,
        notes: document.getElementById('param-notes').value
      };

      try {
        const res = await fetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const result = await res.json();
        renderDirectPlanResults(result);
      } catch (err) {
        alert('Agent execution failed: ' + err);
      } finally {
        btn.innerText = '⚡ Run Autonomous Design Agent';
        btn.disabled = false;
      }
    }

    function renderDirectPlanResults(data) {
      // 1. Status Banner
      const statusCard = document.getElementById('status-card');
      const statusCode = document.getElementById('status-code');
      const statusText = document.getElementById('status-text');
      const statusIcon = document.getElementById('status-icon');

      statusCode.innerText = 'STATUS: ' + (data.status || 'SUCCESS');

      if (data.status === 'SUCCESS') {
        statusCard.className = 'status-banner status-success';
        statusIcon.innerText = '✅';
        statusText.innerText = 'Design Plan Approved: Within Budget & Circulation Safe (<35% Footprint)';
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
      document.getElementById('val-remaining').innerText = 'Remaining: ₹' + (fin.remaining_budget_inr || 0).toLocaleString();
      document.getElementById('val-utilization').innerText = (fin.budget_utilization_percentage || 0) + '% Utilization';

      document.getElementById('val-area').innerText = (spat.room_area_sqm || 0) + ' sqm';
      document.getElementById('val-footprint').innerText = 'Footprint: ' + (spat.furniture_footprint_sqm || 0) + ' sqm';
      document.getElementById('val-occupancy').innerText = (spat.occupancy_percentage || '0%') + ' Occupancy';

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

    // Initialize on page load
    window.onload = () => {
      loadBriefs();
      initChat();
      refreshSessionSidebar();
    };
  </script>
</body>
</html>
"""


class AgentRequestHandler(http.server.SimpleHTTPRequestHandler):
    agent = InteriorDesignAgent()
    conversation_agent = ConversationAgent()

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

        elif parsed.path == "/api/chat/history":
            query_params = urllib.parse.parse_qs(parsed.query)
            session_id = query_params.get("session_id", ["default"])[0]
            history = db.get_chat_history(session_id)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(history).encode("utf-8"))
            return

        elif parsed.path == "/api/chat/session":
            query_params = urllib.parse.parse_qs(parsed.query)
            session_id = query_params.get("session_id", ["default"])[0]
            session = db.get_or_create_session(session_id)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(session).encode("utf-8"))
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

        elif parsed.path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length)
            try:
                payload = json.loads(post_body.decode("utf-8"))
                session_id = payload.get("session_id") or "default-session"
                user_msg = payload.get("message", "")
                result = self.conversation_agent.process_message(session_id, user_msg)

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
    print(f"  ➜ Siya Chat API: http://localhost:{port}/api/chat")
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
