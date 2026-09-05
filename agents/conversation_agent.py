"""
agents/conversation_agent.py - Siya: Conversational AI Interior Design Consultant
Orchestrates the multi-turn conversational flow:
1. Greeting: "Hi, I am Siya, your interior design consultant!"
2. Room Type gate (refuses with "Sorry, I can't design without room type." if confused)
3. Dimensions gate with multi-unit support & accumulation (refuses with "Sorry, we need length, breadth, and height..." if confused)
4. Budget gate (handles ranges/min/max or gracefully skips if confused)
5. Style verification (suggests 2-4 DB styles if unsupported)
6. Must-haves verification (alerts if unlisted and recommends catalog substitutes)
7. Plan synthesis and budget/layout check with dynamic overage explanations and plan edits
8. Real-time session and message persistence in SQLite
"""

import json
import os
import re
from typing import Dict, Any, List, Optional, Tuple

import db
import tools
from .catalog_agent import CatalogAgent
from .budget_agent import BudgetAgent
from .layout_agent import LayoutAgent

DB_PATH = tools.DB_PATH


class ConversationAgent:
    """Siya - Conversational Interior Design Consultant & Dialogue Coordinator."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        self.catalog_agent = CatalogAgent(db_path=self.db_path)
        self.budget_agent = BudgetAgent(db_path=self.db_path)
        self.layout_agent = LayoutAgent(db_path=self.db_path)

    def get_initial_greeting(self, session_id: str) -> Dict[str, Any]:
        """Returns or logs the initial proactive opening message sent by Siya."""
        db.get_or_create_session(session_id, db_path=self.db_path)
        history = db.get_chat_history(session_id, limit=5, db_path=self.db_path)
        first_greeting = "Hi, I am Siya, your interior design consultant!"
        if not history:
            db.add_chat_message(
                session_id,
                sender="siya",
                message=first_greeting,
                metadata={"stage": "GREETING"},
                db_path=self.db_path
            )
            return {
                "session_id": session_id,
                "sender": "siya",
                "message": first_greeting,
                "metadata": {"stage": "GREETING"}
            }
        return history[0]

    def process_message(self, session_id: str, user_text: str) -> Dict[str, Any]:
        """
        Processes an incoming user chat message, updates the session state machine,
        persists history to SQLite, and returns Siya's response.
        """
        # Load or create session from SQLite
        session = db.get_or_create_session(session_id, db_path=self.db_path)
        stage = session.get("stage", "GREETING")

        # Log user message to SQLite in real-time
        db.add_chat_message(session_id, sender="user", message=user_text, db_path=self.db_path)

        cleaned_text = user_text.strip()
        lower_text = cleaned_text.lower()

        response_text = ""
        metadata: Dict[str, Any] = {
            "chips": [],
            "cards": [],
            "stage": stage
        }

        # -------------------------------------------------------------
        # STAGE 1: GREETING
        # -------------------------------------------------------------
        if stage == "GREETING":
            # Check if user message is just a greeting ("Hi", "Hello", etc.)
            greeting_patterns = [r"^(hi|hii|hiii|hello|hey|greetings|namaste)\b"]
            is_simple_greeting = any(re.match(p, lower_text) for p in greeting_patterns)

            # Check if user already provided room type in greeting
            room_found = self._detect_room_type(lower_text)

            if room_found:
                db.update_session(session_id, db_path=self.db_path, room_type=room_found, stage="DIMENSIONS")
                response_text = (
                    f"Great! Let's work on your {room_found}. "
                    "What is length * breadth * height of your room? (You can share in meters, feet, or cm)."
                )
                metadata["chips"] = ["15 * 12 feet", "4.8 * 3.6 meters", "450 * 350 * 280 cm"]
                metadata["stage"] = "DIMENSIONS"
            elif any(p in lower_text for p in ["don't know", "dont know", "confused", "not sure", "no idea"]):
                response_text = "Sorry, I can't design without room type. Please let me know if you want to design a Living Room, Bedroom, Dining, Study, or Kids Room."
                metadata["chips"] = ["Living Room", "Bedroom", "Dining", "Study", "Kids Room"]
                db.update_session(session_id, db_path=self.db_path, stage="ROOM_TYPE")
            elif is_simple_greeting or len(cleaned_text) < 10:
                db.update_session(session_id, db_path=self.db_path, stage="ROOM_TYPE")
                response_text = (
                    "Please let me know the room type you are designing for living room, bedroom, dining, etc."
                )
                metadata["chips"] = ["Living Room", "Bedroom", "Dining", "Study", "Kids Room"]
                metadata["stage"] = "ROOM_TYPE"
            else:
                # User sent something else: prompt for room type
                db.update_session(session_id, db_path=self.db_path, stage="ROOM_TYPE")
                response_text = (
                    "Please let me know the room type you are designing for living room, bedroom, dining, etc."
                )
                metadata["chips"] = ["Living Room", "Bedroom", "Dining", "Study", "Kids Room"]
                metadata["stage"] = "ROOM_TYPE"

        # -------------------------------------------------------------
        # STAGE 2: ROOM TYPE
        # -------------------------------------------------------------
        elif stage == "ROOM_TYPE":
            confused_phrases = ["don't know", "dont know", "confused", "not sure", "no idea", "any room"]
            if any(p in lower_text for p in confused_phrases):
                response_text = "Sorry, I can't design without room type. Please let me know if you want to design a Living Room, Bedroom, Dining, Study, or Kids Room."
                metadata["chips"] = ["Living Room", "Bedroom", "Dining", "Study", "Kids Room"]
            else:
                room_found = self._detect_room_type(lower_text)
                if room_found:
                    db.update_session(session_id, db_path=self.db_path, room_type=room_found, stage="DIMENSIONS")
                    response_text = (
                        f"Great! Let's work on your {room_found}. "
                        "What is length * breadth * height of your room? (Feel free to reply in feet, meters, or cm)."
                    )
                    metadata["chips"] = ["14 * 12 feet", "4.5 * 3.8 meters", "400 * 350 * 280 cm", "I don't know"]
                    metadata["stage"] = "DIMENSIONS"
                else:
                    response_text = "Sorry, I can't design without room type. Please specify whether it is a Living Room, Bedroom, Dining, Study, or Kids Room."
                    metadata["chips"] = ["Living Room", "Bedroom", "Dining", "Study", "Kids Room"]

        # -------------------------------------------------------------
        # STAGE 3: DIMENSIONS (L * B * H)
        # -------------------------------------------------------------
        elif stage == "DIMENSIONS":
            dim_res = self.layout_agent.parse_dimensions(
                user_text,
                current_l=session.get("length_cm"),
                current_w=session.get("width_cm"),
                current_h=session.get("height_cm")
            )

            if dim_res["is_confused"]:
                response_text = "Sorry, we need length, breadth, and height; we can't make an interior design plan without it. Even an estimate (like 12 * 10 feet) will help us get started!"
                metadata["chips"] = ["12 * 10 feet", "15 * 12 feet", "4.5 * 3.5 meters"]
            elif dim_res["is_complete"]:
                l_cm = dim_res["length_cm"]
                w_cm = dim_res["width_cm"]
                h_cm = dim_res["height_cm"] or 280
                area_sqm = round((l_cm * w_cm) / 10000.0, 2)

                db.update_session(
                    session_id,
                    db_path=self.db_path,
                    length_cm=l_cm,
                    width_cm=w_cm,
                    height_cm=h_cm,
                    stage="BUDGET"
                )
                response_text = (
                    f"Got it! Your room dimensions are {l_cm} x {w_cm} x {h_cm} cm (approx {area_sqm} sqm). "
                    "What is your budget for this room? You can mention an exact budget (e.g. ₹2,00,000), a range (between ₹1L and ₹2L), or 'under ₹1.5L'."
                )
                metadata["chips"] = ["Under ₹1.5 Lakhs", "Between ₹1L - ₹2.5L", "Around ₹2,00,000", "I don't have a budget"]
                metadata["stage"] = "BUDGET"
            else:
                # Partial dimensions received (e.g. length received, breadth/height missing)
                missing_str = " and ".join(dim_res["missing_parts"])
                db.update_session(
                    session_id,
                    db_path=self.db_path,
                    length_cm=dim_res.get("length_cm"),
                    width_cm=dim_res.get("width_cm"),
                    height_cm=dim_res.get("height_cm")
                )
                response_text = f"Thanks! I noted that. What is the {missing_str} of the room?"

        # -------------------------------------------------------------
        # STAGE 4: BUDGET
        # -------------------------------------------------------------
        elif stage == "BUDGET":
            b_res = self.budget_agent.parse_budget_input(user_text)
            db.update_session(
                session_id,
                db_path=self.db_path,
                budget_raw=user_text,
                budget_min=b_res.get("budget_min"),
                budget_max=b_res.get("budget_target") or 250000,
                stage="STYLE"
            )

            # Suggest styles from database
            suggested_styles = ["Scandinavian", "Mid-Century", "Contemporary", "Bohemian"]
            styles_str = ", ".join(suggested_styles)

            if b_res["is_skipped"]:
                response_text = (
                    "No problem! We can proceed without a strict budget cap and select balanced, high-value pieces. "
                    f"What style do you prefer? We have great styles like {styles_str}."
                )
            else:
                budget_val = b_res.get("budget_target") or 250000
                response_text = (
                    f"Noted! Budget allocation set to approx ₹{budget_val:,}. "
                    f"What style do you prefer? For example, we offer {styles_str}."
                )

            metadata["chips"] = suggested_styles + ["I am confused"]
            metadata["stage"] = "STYLE"

        # -------------------------------------------------------------
        # STAGE 5: STYLE
        # -------------------------------------------------------------
        elif stage == "STYLE":
            confused_phrases = ["don't know", "dont know", "confused", "not sure", "no idea", "any style", "skip"]
            if any(p in lower_text for p in confused_phrases):
                # Suggest styles from DB
                suggested_styles = ["Scandinavian", "Mid-Century", "Contemporary", "Bohemian"]
                response_text = (
                    f"No worries at all! Here are some popular styles from our catalog: {', '.join(suggested_styles)}. "
                    "Which one of these resonates with you, or shall we go with a timeless Scandinavian look?"
                )
                metadata["chips"] = suggested_styles
            else:
                is_valid, matched_style, suggested_alts = self.catalog_agent.validate_style(user_text)

                if is_valid and matched_style:
                    db.update_session(session_id, db_path=self.db_path, style=matched_style, stage="MUST_HAVES")
                    room_t = session.get("room_type", "Living Room")
                    default_must_haves = self.catalog_agent.get_room_must_haves_suggestions(room_t)

                    response_text = (
                        f"I love the {matched_style} aesthetic! "
                        f"What are your must-haves in your {room_t}? "
                        f"For this room, customers typically choose: {', '.join(default_must_haves)}."
                    )
                    metadata["chips"] = default_must_haves + ["All of these"]
                    metadata["stage"] = "MUST_HAVES"
                else:
                    # Style is NOT present in DB
                    clean_style = re.sub(r"\s+style\b", "", user_text, flags=re.IGNORECASE).strip().title()
                    alts_str = ", ".join(suggested_alts[:3])
                    response_text = (
                        f"We don't have {clean_style} style currently. Do you want to try from {alts_str} styles?"
                    )
                    metadata["chips"] = suggested_alts

        # -------------------------------------------------------------
        # STAGE 6: MUST-HAVES & CONSTRAINTS
        # -------------------------------------------------------------
        elif stage == "MUST_HAVES":
            room_t = session.get("room_type", "Living Room")
            default_must_haves = self.catalog_agent.get_room_must_haves_suggestions(room_t)

            # Check if user asked for external/unlisted item
            has_avail, unlisted_item, rec_item = self.catalog_agent.check_must_have_availability(user_text)

            unlisted_alert = ""
            if not has_avail and unlisted_item:
                sub_name = rec_item.get("name") if rec_item else "our premium in-catalog alternative"
                unlisted_alert = (
                    f"Currently we don't have {unlisted_item} from the must-haves. "
                    f"However, we have recommended {sub_name} as a stylish in-catalog substitute!\n\n"
                )

            # Save must-haves to session
            must_haves_list = [m.strip() for m in user_text.split(",") if m.strip()]
            if not must_haves_list or "all" in lower_text:
                must_haves_list = default_must_haves

            db.update_session(
                session_id,
                db_path=self.db_path,
                must_haves=json.dumps(must_haves_list),
                notes=user_text,
                stage="PLAN_GENERATED"
            )

            # Generate the design plan using the specialist agents!
            plan_result = self._synthesize_plan(session_id)
            db.update_session(session_id, db_path=self.db_path, current_plan_json=json.dumps(plan_result))

            fin = plan_result.get("financial_summary", {})
            spat = plan_result.get("spatial_fit_summary", {})

            # Budget diagnosis
            budget_diag = ""
            if plan_result.get("status") == "BUDGET_DEFICIT_FLAGGED" or fin.get("remaining_budget_inr", 0) < 0:
                budget_diag = (
                    f"⚠️ Budget Notice: The complete set comes to ₹{fin.get('total_spent_inr', 0):,}. "
                    "We have prioritized core foundation pieces and suggested budget-friendly options to keep you on track.\n\n"
                )

            response_text = (
                f"{unlisted_alert}"
                f"🎉 I have put together a customized design plan for your {room_t}!\n\n"
                f"{budget_diag}"
                f"• Theme: {plan_result.get('design_concept', {}).get('theme')}\n"
                f"• Total Spent: ₹{fin.get('total_spent_inr', 0):,} ({fin.get('budget_utilization_percentage')} % utilization)\n"
                f"• Floor Occupancy: {spat.get('occupancy_percentage')} (Circulation safe: {spat.get('circulation_viable')})\n\n"
                "Review the itemized Bill of Quantities (BOQ) below. Would you like to swap any items or adjust the budget?"
            )
            metadata["plan"] = plan_result
            metadata["chips"] = ["Looks great!", "Can we reduce budget?", "Swap sofa", "Start over"]
            metadata["stage"] = "PLAN_REVISION"

        # -------------------------------------------------------------
        # STAGE 7: PLAN REVISION / EDIT PLAN
        # -------------------------------------------------------------
        elif stage in ["PLAN_GENERATED", "PLAN_REVISION"]:
            if "reduce" in lower_text or "cheaper" in lower_text or "budget" in lower_text:
                # User wants to adjust budget
                b_res = self.budget_agent.parse_budget_input(user_text)
                if not b_res["is_skipped"] and b_res.get("budget_target"):
                    db.update_session(session_id, db_path=self.db_path, budget_max=b_res["budget_target"])

                # Re-synthesize with tighter budget
                revised_plan = self._synthesize_plan(session_id, force_cheaper=True)
                db.update_session(session_id, db_path=self.db_path, current_plan_json=json.dumps(revised_plan))
                fin = revised_plan.get("financial_summary", {})

                response_text = (
                    f"I've revised the plan to be more budget-friendly! "
                    f"The new total is ₹{fin.get('total_spent_inr', 0):,} (Remaining: ₹{fin.get('remaining_budget_inr', 0):,}). "
                    "I have updated the BOQ table below."
                )
                metadata["plan"] = revised_plan
                metadata["chips"] = ["Confirm plan", "Looks perfect!", "Start fresh"]
            elif "start over" in lower_text or "restart" in lower_text or "start fresh" in lower_text:
                db.update_session(
                    session_id,
                    db_path=self.db_path,
                    stage="GREETING",
                    room_type=None,
                    length_cm=None,
                    width_cm=None,
                    height_cm=None,
                    budget_max=None,
                    style=None,
                    must_haves="[]",
                    notes=None,
                    current_plan_json=None
                )
                response_text = "Hi, I am Siya, your interior design consultant! What room type are we designing today?"
                metadata["chips"] = ["Living Room", "Bedroom", "Dining", "Study"]
                metadata["stage"] = "ROOM_TYPE"
            else:
                response_text = (
                    "Your customized BOQ plan is saved! If you want to refine anything (e.g. 'swap sofa for leather', "
                    "'make it cheaper', or 'add a floor lamp'), just let me know and I will edit the plan in real-time."
                )
                metadata["chips"] = ["Make it cheaper", "Change style", "Start over"]

        # Log Siya's response to SQLite
        db.add_chat_message(
            session_id,
            sender="siya",
            message=response_text,
            metadata=metadata,
            db_path=self.db_path
        )

        return {
            "session_id": session_id,
            "sender": "siya",
            "message": response_text,
            "metadata": metadata
        }

    def _detect_room_type(self, text: str) -> Optional[str]:
        """Detect room type from text."""
        mapping = {
            "living": "Living Room",
            "hall": "Living Room",
            "drawing": "Living Room",
            "bed": "Bedroom",
            "master": "Bedroom",
            "dining": "Dining",
            "study": "Study",
            "office": "Study",
            "wfh": "Study",
            "kids": "Kids Room",
            "child": "Kids Room"
        }
        for kw, room_name in mapping.items():
            if kw in text:
                return room_name
        return None

    def _synthesize_plan(self, session_id: str, force_cheaper: bool = False) -> Dict[str, Any]:
        """Synthesize plan using catalog_agent, budget_agent, and layout_agent."""
        session = db.get_or_create_session(session_id, db_path=self.db_path)
        room_type = session.get("room_type") or "Living Room"
        length_cm = int(session.get("length_cm") or 450)
        width_cm = int(session.get("width_cm") or 350)
        budget = int(session.get("budget_max") or 200000)
        style = session.get("style") or "Scandinavian"
        notes = session.get("notes") or ""

        # Format brief for underlying agent execution
        brief_payload = {
            "brief_id": f"SESSION-{session_id[:8]}",
            "room_type": room_type,
            "dimensions": [length_cm, width_cm, 280],
            "budget_inr": (budget // 2) if force_cheaper else budget,
            "style": style,
            "must_haves": session.get("must_haves", ""),
            "notes": notes
        }

        from agent import InteriorDesignAgent
        agent = InteriorDesignAgent(db_path=self.db_path)
        return agent.run(brief_payload)
