"""
agents package - Modular Multi-Agent Architecture for Interior Company x Blocks.
Exposes:
- CatalogAgent: Inventory querying, style validation & product substitution
- BudgetAgent: Natural language budget parsing, balance checks & overage trade-offs
- LayoutAgent: Mixed-unit dimension conversion, partial accumulation & 35% footprint check
- ConversationAgent: Siya dialogue coordinator & state manager
"""

from .catalog_agent import CatalogAgent
from .budget_agent import BudgetAgent
from .layout_agent import LayoutAgent
from .conversation_agent import ConversationAgent

__all__ = ["CatalogAgent", "BudgetAgent", "LayoutAgent", "ConversationAgent"]
