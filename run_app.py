"""
run_app.py - Pure Conversational AI Interior Design Consultant (Siya)
Autonomous AI Interior Design Agent for Interior Company x Blocks.

Pure Chat Interface:
  - 100% Conversational, Zero Form Inputs.
  - Proactive AI greeting: Siya initiates the conversation first.
  - Multi-turn dialogue with real-time SQLite catalog search, budget checks, and layout fit verification.
  - Full BOQ plan rendered directly in the conversational stream.

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
  <title>Siya — AI Interior Design Consultant | Interior Company x Blocks</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-base: #090d16;
      --bg-surface: #0f172a;
      --bg-card: #151f32;
      --bg-card-hover: #1e2b45;
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-accent: rgba(99, 102, 241, 0.35);
      --primary: #6366f1;
      --primary-glow: rgba(99, 102, 241, 0.35);
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
      height: 100vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      line-height: 1.6;
      background-image: 
        radial-gradient(circle at 10% 10%, rgba(99, 102, 241, 0.08) 0%, transparent 45%),
        radial-gradient(circle at 90% 90%, rgba(14, 165, 233, 0.06) 0%, transparent 45%);
    }

    /* Top Navigation Header */
    header {
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border-subtle);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 50;
      flex-shrink: 0;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-logo {
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, var(--primary), var(--accent-sky));
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      font-weight: 800;
      color: #fff;
      box-shadow: 0 0 16px var(--primary-glow);
    }

    .brand-text h1 {
      font-family: 'Space Grotesk', sans-serif;
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.3px;
      color: var(--text-main);
    }

    .brand-text p {
      font-size: 11px;
      color: var(--text-muted);
    }

    .header-badges {
      display: flex;
      gap: 8px;
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

    /* Main Chat Layout */
    .app-container {
      flex: 1 1 0;
      display: grid;
      grid-template-columns: 320px 1fr;
      height: calc(100vh - 65px);
      max-height: calc(100vh - 65px);
      min-height: 0;
      overflow: hidden;
    }

    @media (max-width: 900px) {
      .app-container {
        grid-template-columns: 1fr;
      }
      .sidebar {
        display: none !important;
      }
    }

    /* Left Sidebar: Real-Time Passive Memory Card */
    .sidebar {
      background: rgba(15, 23, 42, 0.6);
      border-right: 1px solid var(--border-subtle);
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      overflow-y: auto;
    }

    .sidebar-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 4px;
    }

    .sidebar-title {
      font-family: 'Space Grotesk', sans-serif;
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
    }

    .btn-new-chat {
      background: rgba(99, 102, 241, 0.15);
      border: 1px solid rgba(99, 102, 241, 0.3);
      color: #a5b4fc;
      padding: 6px 12px;
      border-radius: var(--radius-sm);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }

    .btn-new-chat:hover {
      background: var(--primary);
      color: #fff;
      box-shadow: 0 4px 12px var(--primary-glow);
    }

    .card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 16px;
      box-shadow: var(--shadow-sm);
    }

    .card-title {
      font-family: 'Space Grotesk', sans-serif;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .spec-pill {
      background: rgba(99, 102, 241, 0.2);
      color: #a5b4fc;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 10px;
      font-weight: 700;
    }

    .spec-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      font-size: 12px;
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

    .rule-box {
      font-size: 11px;
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

    /* Right Main Chat Section */
    .chat-container {
      display: flex;
      flex-direction: column;
      height: 100%;
      min-height: 0;
      max-height: 100%;
      overflow: hidden;
      background: transparent;
      position: relative;
    }

    /* Chat Stream Header */
    .chat-header {
      padding: 14px 28px;
      background: rgba(15, 23, 42, 0.5);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }

    .consultant-profile {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .consultant-avatar {
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: linear-gradient(135deg, #a855f7, #6366f1);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      box-shadow: 0 0 14px rgba(168, 85, 247, 0.4);
    }

    .consultant-name {
      font-weight: 700;
      font-size: 15px;
      color: var(--text-main);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .consultant-title {
      font-size: 12px;
      color: var(--text-muted);
    }

    .pulse-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background-color: var(--accent-emerald);
      box-shadow: 0 0 8px var(--accent-emerald);
      display: inline-block;
    }

    /* Chat Messages Stream */
    .chat-messages {
      flex: 1 1 0;
      min-height: 0;
      height: 100%;
      padding: 24px 28px 24px 28px;
      overflow-y: scroll;
      overflow-x: hidden;
      display: flex;
      flex-direction: column;
      gap: 20px;
      scroll-behavior: smooth;
      -webkit-overflow-scrolling: touch;
    }

    .chat-messages::-webkit-scrollbar {
      width: 6px;
    }

    .chat-messages::-webkit-scrollbar-track {
      background: rgba(15, 23, 42, 0.3);
    }

    .chat-messages::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.2);
      border-radius: 9999px;
    }

    .chat-messages::-webkit-scrollbar-thumb:hover {
      background: rgba(99, 102, 241, 0.6);
    }

    /* Floating Scroll Controls (Scroll Up & Scroll Down) */
    .scroll-controls {
      position: absolute;
      bottom: 96px;
      right: 28px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      z-index: 25;
    }

    .btn-scroll {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background: #1e293b;
      border: 1px solid rgba(99, 102, 241, 0.4);
      color: #a5b4fc;
      display: none;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      cursor: pointer;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
      transition: all 0.2s ease;
      user-select: none;
    }

    .btn-scroll:hover {
      background: var(--primary);
      color: #fff;
      transform: translateY(-2px);
      box-shadow: 0 6px 20px var(--primary-glow);
    }

    /* Suggestion Chips */
    .chips-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }

    .chip-btn {
      background: rgba(99, 102, 241, 0.12);
      border: 1px solid rgba(99, 102, 241, 0.3);
      color: #c7d2fe;
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      user-select: none;
    }

    .chip-btn:hover {
      background: var(--primary);
      color: #fff;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px var(--primary-glow);
    }

    .message-row {
      display: flex;
      gap: 12px;
      max-width: 88%;
      animation: fadeIn 0.25s ease-out;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .message-row.bot {
      align-self: flex-start;
    }

    .message-row.user {
      align-self: flex-end;
      flex-direction: row-reverse;
    }

    .msg-avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 17px;
      flex-shrink: 0;
    }

    .bot .msg-avatar {
      background: linear-gradient(135deg, #a855f7, #6366f1);
      box-shadow: 0 0 10px rgba(168, 85, 247, 0.3);
    }

    .user .msg-avatar {
      background: linear-gradient(135deg, #3b82f6, #0ea5e9);
      box-shadow: 0 0 10px rgba(14, 165, 233, 0.3);
    }

    .msg-content-wrap {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .msg-sender-name {
      font-size: 11px;
      font-weight: 600;
      color: var(--text-dim);
    }

    .user .msg-sender-name {
      text-align: right;
    }

    .msg-bubble {
      padding: 14px 18px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.6;
      word-break: break-word;
      white-space: pre-wrap;
    }

    .bot .msg-bubble {
      background: #1e293b;
      color: #f1f5f9;
      border-top-left-radius: 4px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    }

    .user .msg-bubble {
      background: linear-gradient(135deg, #4f46e5, #6366f1);
      color: #ffffff;
      border-top-right-radius: 4px;
      box-shadow: 0 4px 16px rgba(79, 70, 229, 0.35);
    }

    /* Typing Indicator Wave */
    .typing-indicator {
      display: none;
      align-items: center;
      gap: 10px;
      padding: 10px 16px;
      background: rgba(30, 41, 59, 0.7);
      border-radius: 14px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      width: fit-content;
      font-size: 12px;
      color: var(--text-muted);
      align-self: flex-start;
      margin-left: 48px;
    }

    .dots-wave {
      display: flex;
      gap: 4px;
      align-items: center;
    }

    .dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background-color: #818cf8;
      animation: bounce 1.2s infinite ease-in-out;
    }

    .dot:nth-child(2) { animation-delay: 0.2s; }
    .dot:nth-child(3) { animation-delay: 0.4s; }

    @keyframes bounce {
      0%, 80%, 100% { transform: translateY(0); }
      40% { transform: translateY(-6px); }
    }

    /* Inline Design Plan Card */
    .boq-plan-card {
      margin-top: 14px;
      background: rgba(10, 14, 23, 0.85);
      border: 1px solid rgba(99, 102, 241, 0.4);
      border-radius: var(--radius-md);
      padding: 18px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .plan-top-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
      padding-bottom: 10px;
    }

    .plan-title {
      font-family: 'Space Grotesk', sans-serif;
      font-weight: 700;
      font-size: 15px;
      color: #a5b4fc;
    }

    .plan-metrics-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      background: rgba(255, 255, 255, 0.03);
      padding: 12px;
      border-radius: var(--radius-sm);
    }

    .plan-metric {
      display: flex;
      flex-direction: column;
    }

    .plan-metric-label {
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .plan-metric-value {
      font-size: 14px;
      font-weight: 700;
      color: #f8fafc;
      margin-top: 2px;
    }

    /* BOQ Items Mini Table */
    .boq-table-wrap {
      overflow-x: auto;
      border-radius: var(--radius-sm);
      border: 1px solid rgba(255, 255, 255, 0.06);
    }

    .boq-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      text-align: left;
    }

    .boq-table th {
      background: rgba(15, 23, 42, 0.9);
      padding: 8px 12px;
      color: var(--text-muted);
      font-weight: 600;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }

    .boq-table td {
      padding: 10px 12px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      color: var(--text-main);
    }

    .boq-table tr:hover {
      background: rgba(255, 255, 255, 0.03);
    }

    .sku-tag {
      font-family: monospace;
      font-size: 11px;
      background: rgba(99, 102, 241, 0.15);
      color: #a5b4fc;
      padding: 2px 6px;
      border-radius: 4px;
    }

    .stock-badge {
      font-size: 10px;
      padding: 2px 6px;
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

    /* Reasoning Steps Accordion */
    .reasoning-toggle {
      font-size: 11px;
      font-weight: 600;
      color: var(--text-dim);
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      margin-top: 4px;
      transition: color 0.2s;
    }

    .reasoning-toggle:hover {
      color: #a5b4fc;
    }

    .reasoning-body {
      display: none;
      flex-direction: column;
      gap: 6px;
      margin-top: 8px;
      font-size: 11px;
      background: rgba(0, 0, 0, 0.3);
      padding: 10px;
      border-radius: 6px;
      border-left: 2px solid var(--primary);
    }

    /* Bottom Chat Input Bar */
    .chat-input-area {
      padding: 16px 28px 20px 28px;
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(16px);
      border-top: 1px solid var(--border-subtle);
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .input-row {
      display: flex;
      gap: 12px;
      align-items: center;
      background: #1e293b;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: var(--radius-md);
      padding: 6px 8px 6px 16px;
      transition: all 0.2s;
    }

    .input-row:focus-within {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
    }

    .chat-input {
      flex: 1;
      background: transparent;
      border: none;
      outline: none;
      color: #fff;
      font-family: inherit;
      font-size: 14px;
      line-height: 1.5;
    }

    .chat-input::placeholder {
      color: var(--text-dim);
    }

    .btn-send {
      background: var(--primary);
      border: none;
      color: white;
      width: 40px;
      height: 40px;
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
      box-shadow: 0 0 12px var(--primary-glow);
    }

    .btn-send:disabled {
      background: var(--text-dim);
      cursor: not-allowed;
      transform: none;
      box-shadow: none;
    }

    .input-hint {
      font-size: 11px;
      color: var(--text-dim);
      text-align: center;
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
        <p>Autonomous AI Interior Design Consultant</p>
      </div>
    </div>

    <div class="header-badges">
      <span class="badge badge-success">
        <span class="pulse-dot"></span> Siya Active
      </span>
      <span class="badge badge-primary">📦 38 Verified SKUs</span>
      <span class="badge badge-primary">📐 Fit Guard (&lt;35%)</span>
    </div>
  </header>

  <!-- Main Application Body -->
  <div class="app-container">
    <!-- Left Sidebar: Real-Time Passive Session Memory -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <span class="sidebar-title">Consultation Session</span>
        <button class="btn-new-chat" onclick="resetChat()">
          <span>+</span> New Chat
        </button>
      </div>

      <!-- Live Room Specs Card -->
      <div class="card">
        <div class="card-title">
          <span>Room Brief Memory</span>
          <span class="spec-pill" id="sidebar-stage">GREETING</span>
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
          <span class="spec-label">Aesthetic Style</span>
          <span class="spec-value" id="spec-style">—</span>
        </div>
        <div class="spec-item">
          <span class="spec-label">Must-Haves</span>
          <span class="spec-value" id="spec-must-haves" style="max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">—</span>
        </div>
      </div>

      <!-- Safety & Guardrail Rules -->
      <div class="card">
        <div class="card-title">Active Safety Engine</div>
        <div class="rule-box">
          <div class="rule-item">
            <span>🛡️</span>
            <span><strong>Civil Safety:</strong> Wall demolition & plumbing changes blocked with structural engineer referrals.</span>
          </div>
          <div class="rule-item">
            <span>📐</span>
            <span><strong>Circulation Fit:</strong> Maximum 35% footprint occupancy to preserve free walkway flow.</span>
          </div>
          <div class="rule-item">
            <span>🔄</span>
            <span><strong>Zero Hallucination:</strong> Unlisted external brands replaced with verified in-catalog items.</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- Right Chat Area -->
    <main class="chat-container">
      <!-- Chat Profile Header -->
      <div class="chat-header">
        <div class="consultant-profile">
          <div class="consultant-avatar">🛋️</div>
          <div>
            <div class="consultant-name">
              <span>Siya</span>
              <span class="spec-pill" style="background: rgba(16, 185, 129, 0.2); color: #34d399;">Senior Consultant</span>
            </div>
            <div class="consultant-title">
              Interior Company x Blocks • Powered by SQLite Catalog & Spatial Fit Engine
            </div>
          </div>
        </div>
      </div>

      <!-- Chat Messages Container -->
      <div class="chat-messages" id="chat-messages" onscroll="handleChatScroll()">
        <!-- Messages will be populated dynamically -->
        <div id="chat-bottom-anchor" style="height: 1px; width: 100%; flex-shrink: 0; margin-top: 4px;"></div>
      </div>

      <!-- Floating Scroll Navigation Controls (Scroll Up & Scroll Down) -->
      <div class="scroll-controls" id="scroll-controls">
        <button class="btn-scroll" id="btn-scroll-top" onclick="scrollToTop(true)" title="Scroll up to top">
          ↑
        </button>
        <button class="btn-scroll" id="btn-scroll-bottom" onclick="scrollToBottom(true)" title="Scroll down to latest">
          ↓
        </button>
      </div>

      <!-- Typing Indicator Wave -->
      <div class="typing-indicator" id="typing-indicator">
        <div class="dots-wave">
          <div class="dot"></div>
          <div class="dot"></div>
          <div class="dot"></div>
        </div>
        <span>Siya is verifying catalog inventory and checking room fit...</span>
      </div>

      <!-- Bottom Chat Input Bar -->
      <div class="chat-input-area">
        <div class="input-row">
          <input 
            type="text" 
            id="chat-input" 
            class="chat-input" 
            placeholder="Type your message to Siya..." 
            autocomplete="off"
          />
          <button class="btn-send" id="btn-send" onclick="handleSendMessage()">
            ➤
          </button>
        </div>
        <div class="input-hint">
          Siya asks questions step-by-step. Reply naturally in feet, meters, or cm. No forms to fill out.
        </div>
      </div>
    </main>
  </div>

  <script>
    // App State
    let currentSessionId = 'siya-' + Math.random().toString(36).substring(2, 9);
    let isProcessing = false;

    // Initialize Chat: Siya greets first!
    async function initChat() {
      showTyping(true);
      try {
        const res = await fetch(`/api/chat/init?session_id=${currentSessionId}`);
        const data = await res.json();
        showTyping(false);
        if (data.message) {
          appendMessage('bot', data.message, data.metadata);
        }
      } catch (err) {
        showTyping(false);
        appendMessage('bot', 'Hi, I am Siya, your interior design consultant!');
      }
      refreshSidebar();
      scrollToBottom(false);
    }

    async function handleSendMessage() {
      if (isProcessing) return;
      const input = document.getElementById('chat-input');
      const text = input.value.trim();
      if (!text) return;

      // 1. Render user message
      appendMessage('user', text);
      input.value = '';

      // 2. Lock input and show typing wave
      isProcessing = true;
      document.getElementById('btn-send').disabled = true;
      showTyping(true);

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: currentSessionId,
            message: text
          })
        });

        const data = await res.json();
        showTyping(false);

        if (data.message) {
          appendMessage('bot', data.message, data.metadata);
        }
      } catch (err) {
        showTyping(false);
        appendMessage('bot', '⚠️ Connection error. Please ensure the server is running.');
      } finally {
        isProcessing = false;
        document.getElementById('btn-send').disabled = false;
        input.focus();
        refreshSidebar();
        scrollToBottom(true);
      }
    }

    function appendMessage(sender, text, metadata = null) {
      const container = document.getElementById('chat-messages');
      const row = document.createElement('div');
      row.className = `message-row ${sender}`;

      const avatar = document.createElement('div');
      avatar.className = 'msg-avatar';
      avatar.innerText = sender === 'bot' ? '🛋️' : '👤';

      const contentWrap = document.createElement('div');
      contentWrap.className = 'msg-content-wrap';

      const senderName = document.createElement('div');
      senderName.className = 'msg-sender-name';
      senderName.innerText = sender === 'bot' ? 'Siya (AI Consultant)' : 'You';

      const bubble = document.createElement('div');
      bubble.className = 'msg-bubble';
      bubble.innerText = text;

      contentWrap.appendChild(senderName);
      contentWrap.appendChild(bubble);

      // Render suggestion chips if available
      if (metadata && metadata.chips && metadata.chips.length > 0 && sender === 'bot') {
        const chipsRow = document.createElement('div');
        chipsRow.className = 'chips-row';
        metadata.chips.forEach(chipText => {
          const chip = document.createElement('button');
          chip.className = 'chip-btn';
          chip.innerText = chipText;
          chip.onclick = () => {
            const input = document.getElementById('chat-input');
            input.value = chipText;
            handleSendMessage();
          };
          chipsRow.appendChild(chip);
        });
        contentWrap.appendChild(chipsRow);
      }

      // If metadata contains a synthesized design plan, render the Itemized BOQ Card
      if (metadata && metadata.plan) {
        const plan = metadata.plan;
        const fin = plan.financial_summary || {};
        const spat = plan.spatial_fit_summary || {};
        const conc = plan.design_concept || {};
        const boq = plan.boq || [];

        const planCard = document.createElement('div');
        planCard.className = 'boq-plan-card';

        // Top Row: Theme & Status
        let boqRowsHtml = '';
        if (boq.length === 0) {
          boqRowsHtml = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 16px;">No items selected (operational scope refusal or budget deficit).</td></tr>';
        } else {
          boq.forEach(item => {
            const price = item.price_inr ? '₹' + item.price_inr.toLocaleString() : 'Quote Req.';
            const stockClass = item.in_stock ? 'stock-in' : 'stock-out';
            const stockLabel = item.in_stock ? 'In Stock' : 'Pre-order';
            boqRowsHtml += `
              <tr>
                <td><span class="sku-tag">${item.item_id}</span></td>
                <td>${item.category}</td>
                <td style="font-weight: 600;">${item.name}</td>
                <td style="color: var(--text-muted); font-size: 11px;">${item.finish || 'Standard'}</td>
                <td style="font-weight: 700; color: #a5b4fc;">${price}</td>
                <td><span class="stock-badge ${stockClass}">${stockLabel}</span></td>
              </tr>
            `;
          });
        }

        // Reasoning steps
        let reasoningStepsHtml = '';
        (plan.reasoning_steps || []).forEach(s => {
          reasoningStepsHtml += `<div><strong>Step ${s.step} [${s.action}]:</strong> ${s.thought}</div>`;
        });

        planCard.innerHTML = `
          <div class="plan-top-row">
            <span class="plan-title">🛋️ ${conc.theme || 'Custom Interior Design Plan'}</span>
            <span class="spec-pill" style="background: rgba(16, 185, 129, 0.2); color: #34d399;">${plan.status}</span>
          </div>

          <div class="plan-metrics-grid">
            <div class="plan-metric">
              <span class="plan-metric-label">Total Spend</span>
              <span class="plan-metric-value">₹${(fin.total_spent_inr || 0).toLocaleString()}</span>
            </div>
            <div class="plan-metric">
              <span class="plan-metric-label">Budget Utilization</span>
              <span class="plan-metric-value">${fin.budget_utilization_percentage || 0}%</span>
            </div>
            <div class="plan-metric">
              <span class="plan-metric-label">Circulation Viability</span>
              <span class="plan-metric-value" style="color: ${spat.circulation_viable ? '#34d399' : '#fb7185'};">
                ${spat.circulation_viable ? 'Safe (<35%)' : 'Overcrowded'} (${spat.occupancy_percentage || '0%'})
              </span>
            </div>
          </div>

          <div style="font-size: 12px; color: var(--text-muted);">
            <strong style="color: var(--text-main);">Curated Palette:</strong> ${conc.palette_and_materials || 'Standard'}
          </div>

          <div class="boq-table-wrap">
            <table class="boq-table">
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Category</th>
                  <th>Product</th>
                  <th>Finish</th>
                  <th>Price</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                ${boqRowsHtml}
              </tbody>
            </table>
          </div>

          ${reasoningStepsHtml ? `
            <div class="reasoning-toggle" onclick="toggleReasoning(this)">
              <span>▶ View ReAct Agent Reasoning Audit</span>
            </div>
            <div class="reasoning-body">
              ${reasoningStepsHtml}
            </div>
          ` : ''}
        `;

        bubble.appendChild(planCard);
      }

      row.appendChild(avatar);
      row.appendChild(contentWrap);

      // Insert message right before the bottom anchor element
      const anchor = document.getElementById('chat-bottom-anchor');
      if (anchor && anchor.parentNode === container) {
        container.insertBefore(row, anchor);
      } else {
        container.appendChild(row);
      }

      // Smooth auto-scroll down to show the new message
      scrollToBottom(true);
    }

    function scrollToBottom(smooth = true) {
      const container = document.getElementById('chat-messages');
      if (!container) return;

      container.scrollTo({
        top: container.scrollHeight + 10000,
        behavior: smooth ? 'smooth' : 'auto'
      });

      requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight + 10000;
        handleChatScroll();
      });

      setTimeout(() => {
        container.scrollTop = container.scrollHeight + 10000;
        handleChatScroll();
      }, 50);

      setTimeout(() => {
        container.scrollTop = container.scrollHeight + 10000;
        handleChatScroll();
      }, 200);
    }

    function scrollToTop(smooth = true) {
      const container = document.getElementById('chat-messages');
      if (!container) return;

      container.scrollTo({
        top: 0,
        behavior: smooth ? 'smooth' : 'auto'
      });

      setTimeout(() => {
        handleChatScroll();
      }, 200);
    }

    function handleChatScroll() {
      const container = document.getElementById('chat-messages');
      const btnBottom = document.getElementById('btn-scroll-bottom');
      const btnTop = document.getElementById('btn-scroll-top');
      if (!container) return;

      const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
      const distanceFromTop = container.scrollTop;

      // Show scroll to bottom button if user scrolled up more than 60px
      if (btnBottom) {
        btnBottom.style.display = distanceFromBottom > 60 ? 'flex' : 'none';
      }

      // Show scroll to top button if user scrolled down more than 150px
      if (btnTop) {
        btnTop.style.display = distanceFromTop > 150 ? 'flex' : 'none';
      }
    }

    function toggleReasoning(elem) {
      const body = elem.nextElementSibling;
      if (body.style.display === 'flex') {
        body.style.display = 'none';
        elem.querySelector('span').innerText = '▶ View ReAct Agent Reasoning Audit';
      } else {
        body.style.display = 'flex';
        elem.querySelector('span').innerText = '▼ Hide ReAct Agent Reasoning Audit';
        scrollToBottom(true);
      }
    }

    function showTyping(show) {
      const indicator = document.getElementById('typing-indicator');
      indicator.style.display = show ? 'flex' : 'none';
      if (show) {
        scrollToBottom(true);
      }
    }

    async function refreshSidebar() {
      try {
        const res = await fetch(`/api/chat/session?session_id=${currentSessionId}`);
        const s = await res.json();
        if (!s) return;

        document.getElementById('sidebar-stage').innerText = s.stage || 'GREETING';
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
        console.error('Error updating sidebar:', err);
      }
    }

    function resetChat() {
      currentSessionId = 'siya-' + Math.random().toString(36).substring(2, 9);
      document.getElementById('chat-messages').innerHTML = '';
      refreshSidebar();
      initChat();
    }

    // Handle Enter key in input
    document.addEventListener('DOMContentLoaded', () => {
      const input = document.getElementById('chat-input');
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          handleSendMessage();
        }
      });
      initChat();
    });
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

        elif parsed.path == "/api/chat/init":
            query_params = urllib.parse.parse_qs(parsed.query)
            session_id = query_params.get("session_id", ["default"])[0]
            init_msg = self.conversation_agent.get_initial_greeting(session_id)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(init_msg).encode("utf-8"))
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

        elif parsed.path == "/api/catalog":
            items = tools.get_all_catalog_items()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(items).encode("utf-8"))
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

        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/chat":
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
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        elif parsed.path == "/api/generate":
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
    print(f"🌐 SIYA AI INTERIOR DESIGN CONSULTANT — SERVER RUNNING")
    print("=" * 80)
    print(f"  ➜ Chat Web Interface: http://localhost:{port}")
    print(f"  ➜ Chat API: http://localhost:{port}/api/chat")
    print(f"  ➜ Catalog Explorer: http://localhost:{port}/api/catalog")
    print("  Press Ctrl+C to stop the server.")
    print("=" * 80 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Siya - Conversational AI Interior Design Consultant")
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
