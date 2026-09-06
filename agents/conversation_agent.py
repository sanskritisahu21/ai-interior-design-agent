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
from .gemini_service import GeminiService

DB_PATH = tools.DB_PATH


class ConversationAgent:
    """Siya - Conversational Interior Design Consultant & Dialogue Coordinator."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        self.catalog_agent = CatalogAgent(db_path=self.db_path)
        self.budget_agent = BudgetAgent(db_path=self.db_path)
        self.layout_agent = LayoutAgent(db_path=self.db_path)
        self.gemini_service = GeminiService()

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
    def _auto_score_session(self, session_id: str) -> None:
        """Automatically evaluates and saves the 14-column scorecard for a completed or revised session."""
        try:
            import eval_scorecard
            eval_scorecard.record_chat_session_scorecard(session_id)
        except Exception:
            pass

    def _is_pure_parameter(self, text: str) -> bool:
        """Checks if text is a single direct parameter like 'Living Room', '200 290 310', '200000', 'Scandinavian'."""
        clean = text.strip()
        lower = clean.lower()
        if lower in ["living room", "living", "bedroom", "master bedroom", "dining room", "dining", "study room", "study", "kids room", "kids"]:
            return True
        if re.match(r"^\d+\s*[\*xX\s,]\s*\d+(?:\s*[\*xX\s,]\s*\d+)?\s*(?:cm|ft|feet|meters|m)?$", clean, re.I):
            return True
        if re.match(r"^\d+$", clean):
            return True
        if lower in ["scandinavian", "contemporary", "mid-century", "bohemian", "industrial", "minimalist", "traditional", "coastal"]:
            return True
        return False

    def _is_question_or_conversational(self, text: str, stage: str = "") -> bool:
        """Determines if the user's input is a conversational inquiry, design question, hesitation, or advice request."""
        clean = text.strip()
        lower = clean.lower()

        # Pure parameter bypass: raw numbers, direct DB styles, direct room clicks, or comma-separated item lists
        if self._is_pure_parameter(clean):
            return False

        # In STYLE stage, let deterministic style validation handle direct style attempts (e.g. "Gothic", "Art Deco", "Scandinavian")
        if stage == "STYLE":
            hesitation_tokens = ["don't know", "dont know", "not sure", "confused", "no idea", "what do you recommend", "suggest", "choice", "help me choose", "you choose", "choose for me", "surprise me", "options", "what styles", "which style"]
            if "?" not in clean and not any(h in lower for h in hesitation_tokens):
                return False

        # In MUST_HAVES or if text is a comma-separated item list, let deterministic coverage handle it unless user asked a question
        if stage == "MUST_HAVES" or ("," in clean and len(clean.split(",")) >= 2):
            if "?" not in clean:
                return False

        # In PLAN_GENERATED / PLAN_REVISION, let deterministic tools handle add/remove/swap/cheaper/reset commands
        if stage in ["PLAN_GENERATED", "PLAN_REVISION"]:
            if self._extract_add_target(clean) or self._extract_remove_target(clean):
                return False
            if any(w in lower for w in ["swap", "replace", "reduce", "cheaper", "start over", "restart", "looks great", "looks perfect", "confirm plan", "proceed"]):
                return False

        # If user message is just a standalone greeting ("hi", "hello") at GREETING stage, let standard opening flow handle it
        if stage == "GREETING" and any(re.match(p, lower) for p in [r"^(hi|hii|hiii|hello|hey|greetings|namaste)$"]):
            return False

        # Any other message (questions, "hotel", "hotel room", "Yeah", "yes", "i don't have any choice", "you choose", "surprise me", "minimal", etc.) is conversational!
        return True

    def _handle_gemini_turn(
        self,
        session_id: str,
        user_text: str,
        session: Dict[str, Any],
        current_stage: str
    ) -> Optional[Dict[str, Any]]:
        """
        Processes a conversational turn using Gemini:
        1. Generates rich, empathetic, and knowledgeable interior design advice.
        2. Intelligently updates session entities (room, dimensions, budget, style) if extracted.
        3. Coordinates with existing catalog and BOQ synthesis tools.
        """
        if not self.gemini_service.is_configured():
            return None

        # Fetch recent chat history
        history = db.get_chat_history(session_id, limit=8, db_path=self.db_path)

        room_t = session.get("room_type") or "Living Room"
        categories = self.catalog_agent.get_categories_for_room(room_t)
        catalog_info = {
            "styles": ["Scandinavian", "Contemporary", "Mid-Century", "Bohemian", "Industrial", "Minimalist"],
            "categories": categories[:8]
        }

        try:
            gemini_res = self.gemini_service.generate_chat_reply(
                user_message=user_text,
                chat_history=history,
                session_state=session,
                catalog_info=catalog_info
            )
        except Exception:
            return None

        if not gemini_res or not isinstance(gemini_res, dict) or not gemini_res.get("reply"):
            return None

        reply_text = gemini_res.get("reply", "").strip()
        chips = gemini_res.get("chips", []) or []
        extracted = gemini_res.get("extracted", {}) or {}
        action = gemini_res.get("action", "CONTINUE")

        # 1. Update session state with any newly extracted entities
        new_updates = {}
        if extracted.get("room_type") and not session.get("room_type"):
            detected_room = self._detect_room_type(extracted["room_type"]) or extracted["room_type"]
            new_updates["room_type"] = detected_room
            if current_stage in ["GREETING", "ROOM_TYPE"]:
                new_updates["stage"] = "DIMENSIONS"

        if extracted.get("length_cm") and extracted.get("width_cm"):
            new_updates["length_cm"] = int(extracted["length_cm"])
            new_updates["width_cm"] = int(extracted["width_cm"])
            new_updates["height_cm"] = int(extracted.get("height_cm") or session.get("height_cm") or 280)
            if current_stage in ["GREETING", "ROOM_TYPE", "DIMENSIONS"]:
                new_updates["stage"] = "BUDGET"

        if extracted.get("budget_inr"):
            new_updates["budget_max"] = int(extracted["budget_inr"])
            if current_stage in ["GREETING", "ROOM_TYPE", "DIMENSIONS", "BUDGET"]:
                new_updates["stage"] = "STYLE"

        if extracted.get("style"):
            is_valid, matched, alts = self.catalog_agent.validate_style(extracted["style"])
            if is_valid and matched:
                new_updates["style"] = matched
                if current_stage in ["GREETING", "ROOM_TYPE", "DIMENSIONS", "BUDGET", "STYLE"]:
                    new_updates["stage"] = "MUST_HAVES"
            else:
                clean_style = re.sub(r"[^a-zA-Z0-9\s\-]", "", extracted["style"]).strip()
                alts_str = ", ".join(alts[:3]) if alts else "Scandinavian, Mid-Century, Contemporary"
                reply_text = f"We don't have {clean_style} style currently. Do you want to try from {alts_str} styles?"
                chips = alts or ["Scandinavian", "Mid-Century", "Contemporary", "Bohemian"]

        if extracted.get("must_haves"):
            if isinstance(extracted["must_haves"], list):
                new_updates["must_haves"] = json.dumps(extracted["must_haves"])
            else:
                new_updates["must_haves"] = json.dumps([str(extracted["must_haves"])])

        if new_updates:
            db.update_session(session_id, db_path=self.db_path, **new_updates)
            session = db.get_or_create_session(session_id, db_path=self.db_path)

        metadata: Dict[str, Any] = {
            "chips": chips or ["Living Room", "Bedroom", "Dining", "Study"],
            "cards": [],
            "stage": session.get("stage", current_stage)
        }

        # 2. Attach or handle plan if applicable
        raw_plan = session.get("current_plan_json")
        current_plan = json.loads(raw_plan) if raw_plan else None

        # Check if plan should be synthesized
        if action == "GENERATE_PLAN" or (
            session.get("room_type") and 
            session.get("length_cm") and 
            session.get("width_cm") and 
            session.get("style") and 
            not current_plan and
            current_stage in ["MUST_HAVES", "STYLE"]
        ):
            current_plan = self._synthesize_plan(session_id)
            db.update_session(session_id, db_path=self.db_path, current_plan_json=json.dumps(current_plan), stage="PLAN_REVISION")
            self._auto_score_session(session_id)
            metadata["stage"] = "PLAN_REVISION"

            # Format standardized deterministic BOQ response rather than Gemini freeform essay
            coverage = self.catalog_agent.check_must_haves_coverage(user_text, current_plan.get("boq", []), room_type=room_t)
            if coverage["has_unavailable"]:
                unavail_str = ", ".join(coverage["unavailable_items"])
                avail_str = ", ".join(coverage["available_items"])
                intro_text = (
                    f"We don't have {unavail_str} in our catalog for {room_t}.\n"
                    f"Here is your customized interior design plan with the available items: {avail_str}."
                )
            else:
                intro_text = f"🎉 Here is your customized interior design plan for your {room_t}!"

            recs = current_plan.get("recommendations", {})
            rec_item = recs.get("item_recommendation", "")
            rec_style = recs.get("style_recommendation", "")
            rec_color = recs.get("color_recommendation", "")

            reply_text = (
                f"{intro_text}\n\n"
                f"💡 Recommendations:\n"
                f"• Items: {rec_item}\n"
                f"• Style: {rec_style}\n"
                f"• Color & Finish: {rec_color}\n\n"
                "Review the complete 9-field itemized Bill of Quantities (BOQ) below. Would you like to swap any items, change styles, or adjust the budget?"
            )
            chips = ["Looks great!", "Can we reduce budget?", "Swap sofa", "Start over"]

        if current_plan:
            metadata["plan"] = current_plan

        # Log Siya's response to SQLite
        db.add_chat_message(
            session_id,
            sender="siya",
            message=reply_text,
            metadata=metadata,
            db_path=self.db_path
        )

        return {
            "session_id": session_id,
            "sender": "siya",
            "message": reply_text,
            "metadata": metadata
        }

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

        # Operational Guardrails Pre-flight Audit
        guardrail_trip = self._check_negative_guardrails(cleaned_text)
        if guardrail_trip:
            status_code, refusal_msg = guardrail_trip
            db.add_chat_message(session_id, sender="siya", message=refusal_msg, db_path=self.db_path)
            return {
                "session_id": session_id,
                "sender": "siya",
                "message": refusal_msg,
                "metadata": {
                    "stage": stage,
                    "guardrail_triggered": status_code,
                    "chips": ["Living Room", "Bedroom", "Dining", "Study"] if stage in ["GREETING", "ROOM_TYPE"] else []
                }
            }

        # Check if user message is a conversational question / inquiry
        if self.gemini_service.is_configured() and self._is_question_or_conversational(cleaned_text, stage):
            gemini_res = self._handle_gemini_turn(session_id, cleaned_text, session, stage)
            if gemini_res:
                return gemini_res

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
                    if self.gemini_service.is_configured():
                        gemini_res = self._handle_gemini_turn(session_id, cleaned_text, session, stage)
                        if gemini_res:
                            return gemini_res
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
                if self.gemini_service.is_configured():
                    gemini_res = self._handle_gemini_turn(session_id, cleaned_text, session, stage)
                    if gemini_res:
                        return gemini_res
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
                # Partial dimensions received (e.g. length and breadth received, height missing)
                l_cm = dim_res.get("length_cm")
                w_cm = dim_res.get("width_cm")
                h_cm = dim_res.get("height_cm")

                db.update_session(
                    session_id,
                    db_path=self.db_path,
                    length_cm=l_cm,
                    width_cm=w_cm,
                    height_cm=h_cm
                )

                if l_cm and w_cm and not h_cm:
                    response_text = f"Got length and breadth ({l_cm} x {w_cm} cm). What is the height of your room?"
                    metadata["chips"] = ["280 cm (Standard)", "300 cm", "9 feet", "10 feet"]
                elif l_cm and not w_cm:
                    response_text = f"Thanks! I noted length as {l_cm} cm. What is the breadth and height of the room?"
                    metadata["chips"] = ["210 cm", "10 feet", "12 feet"]
                elif w_cm and not l_cm:
                    response_text = f"Thanks! I noted breadth as {w_cm} cm. What is the length and height of the room?"
                    metadata["chips"] = ["200 cm", "12 feet", "15 feet"]
                elif h_cm and not l_cm and not w_cm:
                    response_text = f"Thanks! I noted height as {h_cm} cm. What is the length and breadth of the room?"
                    metadata["chips"] = ["200 210 cm", "15 * 12 feet"]
                else:
                    missing_str = " and ".join(dim_res["missing_parts"])
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
            confused_phrases = [
                "don't know", "dont know", "confused", "not sure", "no idea", "any style",
                "skip", "no choice", "don't have any choice", "dont have any choice",
                "have no choice", "you choose", "you decide", "you pick", "surprise me", "whatever"
            ]
            affirmative_phrases = ["yeah", "yes", "sure", "ok", "okay", "yup", "yep", "go ahead", "sounds good", "let's do it", "lets do it", "that works", "perfect"]
            if lower_text in affirmative_phrases:
                # User affirmed default recommendation (e.g. Scandinavian)
                matched_style = "Scandinavian"
                db.update_session(session_id, db_path=self.db_path, style=matched_style, stage="MUST_HAVES")
                room_t = session.get("room_type", "Living Room")
                default_must_haves = self.catalog_agent.get_room_must_haves_suggestions(room_t)
                response_text = (
                    f"Understood. We will design your {room_t} with a refined {matched_style} aesthetic. "
                    f"What are your essential must-have items for this {room_t}? "
                    f"Clients commonly select: {', '.join(default_must_haves)}."
                )
                metadata["chips"] = default_must_haves + ["All of these"]
                metadata["stage"] = "MUST_HAVES"
            elif any(p in lower_text for p in confused_phrases):
                if self.gemini_service.is_configured():
                    gemini_res = self._handle_gemini_turn(session_id, cleaned_text, session, stage)
                    if gemini_res:
                        return gemini_res
                # Suggest styles from DB
                suggested_styles = ["Scandinavian", "Mid-Century", "Contemporary", "Bohemian"]
                response_text = (
                    f"Certainly. Here are our featured interior styles from the catalog: {', '.join(suggested_styles)}. "
                    "Which aesthetic do you prefer, or shall we proceed with a signature Scandinavian design?"
                )
                metadata["chips"] = suggested_styles
            else:
                is_valid, matched_style, suggested_alts = self.catalog_agent.validate_style(user_text)

                if is_valid and matched_style:
                    db.update_session(session_id, db_path=self.db_path, style=matched_style, stage="MUST_HAVES")
                    room_t = session.get("room_type", "Living Room")
                    default_must_haves = self.catalog_agent.get_room_must_haves_suggestions(room_t)

                    response_text = (
                        f"A {matched_style} aesthetic is an excellent choice for your {room_t}. "
                        f"What are your essential must-haves for this room? "
                        f"Clients commonly select: {', '.join(default_must_haves)}."
                    )
                    metadata["chips"] = default_must_haves + ["All of these"]
                    metadata["stage"] = "MUST_HAVES"
                else:
                    if self.gemini_service.is_configured():
                        gemini_res = self._handle_gemini_turn(session_id, cleaned_text, session, stage)
                        if gemini_res:
                            return gemini_res
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
            self._auto_score_session(session_id)

            recs = plan_result.get("recommendations", {})
            boq = plan_result.get("boq", [])

            # Check coverage of requested must-haves vs catalog & plan
            coverage = self.catalog_agent.check_must_haves_coverage(user_text, boq, room_type=room_t)

            if coverage["has_unavailable"]:
                unavail_str = ", ".join(coverage["unavailable_items"])
                avail_str = ", ".join(coverage["available_items"])
                intro_text = (
                    f"We don't have {unavail_str} in our catalog for {room_t}.\n"
                    f"Here is your customized interior design plan with the available items: {avail_str}."
                )
            else:
                intro_text = f"🎉 Here is your customized interior design plan for your {room_t}!"

            # Brand substitutions note if applicable
            for orig_brand, sub_brand in coverage.get("brand_substitutions", []):
                intro_text += f"\n(Note: Substituted external {orig_brand} with verified in-catalog {sub_brand})"

            rec_item = recs.get("item_recommendation", "")
            rec_style = recs.get("style_recommendation", "")
            rec_color = recs.get("color_recommendation", "")

            response_text = (
                f"{intro_text}\n\n"
                f"💡 Recommendations:\n"
                f"• Items: {rec_item}\n"
                f"• Style: {rec_style}\n"
                f"• Color & Finish: {rec_color}\n\n"
                "Review the complete 9-field itemized Bill of Quantities (BOQ) below. Would you like to swap any items, change styles, or adjust the budget?"
            )
            metadata["plan"] = plan_result
            metadata["chips"] = ["Looks great!", "Can we reduce budget?", "Swap sofa", "Start over"]
            metadata["stage"] = "PLAN_REVISION"

        # -------------------------------------------------------------
        # STAGE 7: PLAN REVISION / EDIT PLAN
        # -------------------------------------------------------------
        elif stage in ["PLAN_GENERATED", "PLAN_REVISION"]:
            room_t = session.get("room_type") or "Living Room"
            length_cm = int(session.get("length_cm") or 450)
            width_cm = int(session.get("width_cm") or 350)
            budget_val = int(session.get("budget_max") or 200000)
            pref_style = session.get("style") or "Scandinavian"

            # Load current plan
            raw_plan = session.get("current_plan_json")
            if raw_plan:
                try:
                    plan = json.loads(raw_plan)
                except Exception:
                    plan = self._synthesize_plan(session_id)
            else:
                plan = self._synthesize_plan(session_id)

            # Intent target extractions
            rem_target = self._extract_remove_target(lower_text)
            add_target = self._extract_add_target(lower_text)

            # If user directly typed an item name or category (e.g. "armchair", "arm chair", "bookshelf")
            if not add_target and not rem_target and len(cleaned_text.split()) <= 4:
                probe = self.catalog_agent.find_catalog_item_for_room(lower_text, room_type=room_t, style=pref_style)
                if probe:
                    add_target = lower_text

            # 1. Reset / restart conversation
            if "start over" in lower_text or "restart" in lower_text or "start fresh" in lower_text:
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

            # 2. Confirmation
            elif any(p in lower_text for p in ["looks great", "looks perfect", "looks good", "confirm plan", "proceed", "finalize", "i like it"]):
                self._auto_score_session(session_id)
                response_text = (
                    "🎉 Fantastic! Your customized BOQ interior plan is confirmed and ready. "
                    "If you ever want to make changes (like adding, removing, or swapping items), just send me a message anytime!"
                )
                metadata["plan"] = plan
                metadata["chips"] = ["Add an item", "Remove an item", "Make it cheaper", "Start fresh"]

            # 3. Compound remove & add in one instruction (e.g. "remove coffee table and add armchair")
            elif re.search(r"\b(?:remove|delete|drop)\s+(?:a\s+|an\s+|the\s+)?([a-z0-9\s\-]+?)\s+(?:and|&)\s+(?:also\s+)?(?:add|include)\s+(?:a\s+|an\s+|the\s+)?([a-z0-9\s\-]+)", lower_text):
                compound_m = re.search(r"\b(?:remove|delete|drop)\s+(?:a\s+|an\s+|the\s+)?([a-z0-9\s\-]+?)\s+(?:and|&)\s+(?:also\s+)?(?:add|include)\s+(?:a\s+|an\s+|the\s+)?([a-z0-9\s\-]+)", lower_text)
                rem_target = compound_m.group(1).strip()
                add_target = compound_m.group(2).strip()

                rem_item, new_boq = self._find_and_remove_boq_item(plan.get("boq", []), rem_target)
                if rem_item:
                    plan["boq"] = new_boq

                added_item = self.catalog_agent.find_catalog_item_for_room(add_target, room_type=room_t, style=pref_style)
                if added_item:
                    plan["boq"].append(self._create_boq_row(added_item, preferred_style=pref_style))

                plan = self._recalculate_plan_metrics(plan, length_cm, width_cm, budget_val, pref_style, room_type=room_t)
                db.update_session(session_id, db_path=self.db_path, current_plan_json=json.dumps(plan))
                self._auto_score_session(session_id)

                fin = plan["financial_summary"]
                rem_b = fin["remaining_budget_inr"]
                b_status = f"₹{fin['total_spent_inr']:,} (₹{rem_b:,} remaining within budget)" if rem_b >= 0 else f"₹{fin['total_spent_inr']:,} (exceeds budget by ₹{abs(rem_b):,})"
                recs = plan["recommendations"]

                status_lines = []
                if rem_item:
                    status_lines.append(f"• Removed: {rem_item['name']} ({rem_item['category']})")
                if added_item:
                    status_lines.append(f"• Added: {added_item['name']} ({added_item['category']})")
                elif not added_item:
                    status_lines.append(f"• Could not add '{add_target}' (not available in {room_t} catalog)")

                response_text = (
                    f"Updated your design plan:\n" + "\n".join(status_lines) + f"\n\nYour updated total spend is {b_status}.\n\n"
                    f"💡 Recommendations:\n"
                    f"• Items: {recs.get('item_recommendation', '')}\n"
                    f"• Style: {recs.get('style_recommendation', '')}\n"
                    f"• Color & Finish: {recs.get('color_recommendation', '')}\n\n"
                    "The updated 9-field BOQ table has been rendered below."
                )
                metadata["plan"] = plan
                metadata["chips"] = ["Looks great!", "Add an item", "Remove an item", "Make it cheaper", "Start fresh"]

            # 4. SWAP / REPLACE (e.g. "swap sofa for leather sofa", "replace coffee table with side table")
            elif re.search(r"\b(?:swap|replace|change)\s+(?:the\s+)?([a-z0-9\s\-]+?)\s+(?:for|with|to)\s+(?:a\s+|an\s+|the\s+)?([a-z0-9\s\-]+)", lower_text):
                swap_m = re.search(r"\b(?:swap|replace|change)\s+(?:the\s+)?([a-z0-9\s\-]+?)\s+(?:for|with|to)\s+(?:a\s+|an\s+|the\s+)?([a-z0-9\s\-]+)", lower_text)
                old_target = swap_m.group(1).strip()
                new_target = swap_m.group(2).strip()

                new_cat_item = self.catalog_agent.find_catalog_item_for_room(new_target, room_type=room_t, style=pref_style)
                if not new_cat_item:
                    room_categories = self.catalog_agent.get_categories_for_room(room_t)
                    response_text = (
                        f"We don't have '{new_target}' in our catalog for {room_t}. "
                        f"Available categories for {room_t} include: {', '.join(room_categories[:6])}."
                    )
                    metadata["plan"] = plan
                    metadata["chips"] = [f"Add {c}" for c in room_categories[:3]] + ["Looks great!"]
                else:
                    rem_item, new_boq = self._find_and_remove_boq_item(plan.get("boq", []), old_target)
                    plan["boq"] = new_boq
                    plan["boq"].append(self._create_boq_row(new_cat_item, preferred_style=pref_style))
                    plan = self._recalculate_plan_metrics(plan, length_cm, width_cm, budget_val, pref_style, room_type=room_t)
                    db.update_session(session_id, db_path=self.db_path, current_plan_json=json.dumps(plan))
                    self._auto_score_session(session_id)

                    fin = plan["financial_summary"]
                    rem_b = fin["remaining_budget_inr"]
                    b_status = f"₹{fin['total_spent_inr']:,} (₹{rem_b:,} remaining within budget)" if rem_b >= 0 else f"₹{fin['total_spent_inr']:,} (exceeds budget by ₹{abs(rem_b):,})"
                    recs = plan["recommendations"]

                    rem_msg = f"Replaced {rem_item['name']}" if rem_item else f"Replaced {old_target}"
                    response_text = (
                        f"🔄 {rem_msg} with {new_cat_item['name']} ({new_cat_item['category']})!\n"
                        f"Your updated total spend is {b_status}.\n\n"
                        f"💡 Recommendations:\n"
                        f"• Items: {recs.get('item_recommendation', '')}\n"
                        f"• Style: {recs.get('style_recommendation', '')}\n"
                        f"• Color & Finish: {recs.get('color_recommendation', '')}\n\n"
                        "The updated 9-field BOQ table has been rendered below."
                    )
                    metadata["plan"] = plan
                    metadata["chips"] = ["Looks great!", "Add an item", "Remove an item", "Make it cheaper"]

            # 5. REMOVE intent (e.g. "remove coffee table", "delete rug", "drop floor lamp", "don't want coffee table")
            elif rem_target:
                raw_target = rem_target
                clean_target = re.sub(r"\b(from the room|from the plan|in the room|in the plan|please|as well|also)\b", "", raw_target, flags=re.IGNORECASE).strip().strip("?.!,")

                candidates = [re.sub(r"^(?:a|an|the|some)\s+", "", c.strip(), flags=re.IGNORECASE).strip() for c in re.split(r",|\s+and\s+|\s+&\s+", clean_target) if c.strip()]
                removed_items = []
                missing_items = []

                for cand in candidates:
                    rem_item, new_boq = self._find_and_remove_boq_item(plan.get("boq", []), cand)
                    if rem_item:
                        plan["boq"] = new_boq
                        removed_items.append(rem_item)
                    else:
                        missing_items.append(cand)

                if not removed_items:
                    current_items = ", ".join([it.get("name", it.get("category", "")) for it in plan.get("boq", [])])
                    response_text = (
                        f"'{clean_target}' was not found in your current design plan. "
                        f"Your plan currently includes: {current_items}."
                    )
                    metadata["plan"] = plan
                    metadata["chips"] = ["Looks great!", "Make it cheaper", "Start over"]
                else:
                    plan = self._recalculate_plan_metrics(plan, length_cm, width_cm, budget_val, pref_style, room_type=room_t)
                    db.update_session(session_id, db_path=self.db_path, current_plan_json=json.dumps(plan))
                    self._auto_score_session(session_id)

                    fin = plan["financial_summary"]
                    rem_b = fin["remaining_budget_inr"]
                    b_status = f"₹{fin['total_spent_inr']:,} (₹{rem_b:,} remaining within budget)" if rem_b >= 0 else f"₹{fin['total_spent_inr']:,} (exceeds budget by ₹{abs(rem_b):,})"
                    recs = plan["recommendations"]

                    rem_names = ", ".join([f"{it['name']} ({it['category']})" for it in removed_items])
                    missing_msg = f" (Note: {', '.join(missing_items)} was not in plan)" if missing_items else ""

                    response_text = (
                        f"🗑️ Removed {rem_names} from your design plan.{missing_msg}\n"
                        f"Your updated total spend is {b_status}.\n\n"
                        f"💡 Recommendations:\n"
                        f"• Items: {recs.get('item_recommendation', '')}\n"
                        f"• Style: {recs.get('style_recommendation', '')}\n"
                        f"• Color & Finish: {recs.get('color_recommendation', '')}\n\n"
                        "The updated 9-field itemized Bill of Quantities (BOQ) is rendered below."
                    )
                    metadata["plan"] = plan
                    metadata["chips"] = ["Looks great!", "Add an item", "Make it cheaper", "Start over"]

            # 6. ADD intent (e.g. "add an armchair", "add arm chair", "why are you not adding armchair?", "can we add a rug", "add floor lamp", "add jacuzzi")
            elif add_target:
                raw_target = add_target
                clean_target = re.sub(r"\b(to the room|to the plan|in the room|in the plan|please|as well|also)\b", "", raw_target, flags=re.IGNORECASE).strip().strip("?.!,")

                candidates = [re.sub(r"^(?:a|an|the|some)\s+", "", c.strip(), flags=re.IGNORECASE).strip() for c in re.split(r",|\s+and\s+|\s+&\s+", clean_target) if c.strip()]
                added_items = []
                missing_items = []

                for cand in candidates:
                    matched_item = self.catalog_agent.find_catalog_item_for_room(cand, room_type=room_t, style=pref_style)
                    if matched_item:
                        new_row = self._create_boq_row(matched_item, preferred_style=pref_style)
                        plan["boq"].append(new_row)
                        added_items.append(matched_item)
                    else:
                        missing_items.append(cand)

                if not added_items:
                    # Item is NOT present in catalog for that room
                    room_categories = self.catalog_agent.get_categories_for_room(room_t)
                    cats_preview = ", ".join(room_categories[:6])
                    response_text = (
                        f"We don't have '{clean_target}' in our catalog for {room_t}. "
                        f"You can choose to add from our available categories for {room_t}: {cats_preview}, and more."
                    )
                    metadata["plan"] = plan
                    metadata["chips"] = [f"Add {c}" for c in room_categories[:3]] + ["Looks great!"]
                else:
                    plan = self._recalculate_plan_metrics(plan, length_cm, width_cm, budget_val, pref_style, room_type=room_t)
                    db.update_session(session_id, db_path=self.db_path, current_plan_json=json.dumps(plan))
                    self._auto_score_session(session_id)

                    fin = plan["financial_summary"]
                    rem_b = fin["remaining_budget_inr"]
                    b_status = f"₹{fin['total_spent_inr']:,} (₹{rem_b:,} remaining within budget)" if rem_b >= 0 else f"₹{fin['total_spent_inr']:,} (exceeds budget by ₹{abs(rem_b):,})"
                    recs = plan["recommendations"]

                    added_names = ", ".join([f"{it['name']} ({it['category']})" for it in added_items])
                    missing_msg = f"\n(Note: We don't have {', '.join(missing_items)} in our catalog for {room_t})" if missing_items else ""

                    spatial = plan.get("spatial_fit_summary", {})
                    spatial_alert = ""
                    if not spatial.get("circulation_viable", True):
                        spatial_alert = f"\n⚠️ Spatial Notice: Furniture footprint is at {spatial.get('occupancy_percentage', 'elevated level')}. Walkway circulation may be tight."

                    budget_alert = ""
                    if rem_b < 0:
                        budget_alert = f"\n⚠️ Budget Notice: This addition exceeds your allocated budget of ₹{budget_val:,} by ₹{abs(rem_b):,}."

                    response_text = (
                        f"✅ Added {added_names} to your design plan!{missing_msg}{budget_alert}{spatial_alert}\n"
                        f"Your updated total spend is {b_status}.\n\n"
                        f"💡 Recommendations:\n"
                        f"• Items: {recs.get('item_recommendation', '')}\n"
                        f"• Style: {recs.get('style_recommendation', '')}\n"
                        f"• Color & Finish: {recs.get('color_recommendation', '')}\n\n"
                        "The updated 9-field itemized Bill of Quantities (BOQ) is rendered below."
                    )
                    metadata["plan"] = plan
                    metadata["chips"] = ["Looks great!", "Add another item", "Remove an item", "Make it cheaper", "Start fresh"]

            # 7. Check budget reduction / cheaper
            elif "reduce" in lower_text or "cheaper" in lower_text or "budget" in lower_text:
                b_res = self.budget_agent.parse_budget_input(user_text)
                if not b_res["is_skipped"] and b_res.get("budget_target"):
                    db.update_session(session_id, db_path=self.db_path, budget_max=b_res["budget_target"])

                revised_plan = self._synthesize_plan(session_id, force_cheaper=True)
                db.update_session(session_id, db_path=self.db_path, current_plan_json=json.dumps(revised_plan))
                recs = revised_plan.get("recommendations", {})

                rec_item = recs.get("item_recommendation", "")
                rec_style = recs.get("style_recommendation", "")
                rec_color = recs.get("color_recommendation", "")

                response_text = (
                    "I've revised the plan to be more budget-friendly!\n\n"
                    f"💡 Recommendations:\n"
                    f"• Items: {rec_item}\n"
                    f"• Style: {rec_style}\n"
                    f"• Color & Finish: {rec_color}\n\n"
                    "The updated 9-field BOQ table has been rendered below."
                )
                metadata["plan"] = revised_plan
                metadata["chips"] = ["Confirm plan", "Looks perfect!", "Start fresh"]

            # 8. Fallback
            else:
                if self.gemini_service.is_configured():
                    gemini_res = self._handle_gemini_turn(session_id, cleaned_text, session, stage)
                    if gemini_res:
                        return gemini_res
                response_text = (
                    "Your customized BOQ plan is saved! You can ask to add any item (e.g. 'add an armchair', 'add a bookshelf'), "
                    "remove any item (e.g. 'remove coffee table'), swap items, or adjust your budget."
                )
                metadata["plan"] = plan
                metadata["chips"] = ["Add an armchair", "Remove coffee table", "Make it cheaper", "Start over"]

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
            "guest": "Bedroom",
            "hotel": "Bedroom",
            "suite": "Bedroom",
            "resort": "Bedroom",
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
        res = agent.run(brief_payload)

        # Fallback guard: Ensure chat users ALWAYS receive a valid, complete BOQ plan
        if not res.get("boq"):
            brief_payload["notes"] = "compact space-conscious layout"
            brief_payload["must_haves"] = ""
            fallback_res = agent.run(brief_payload)
            if fallback_res.get("boq"):
                res = fallback_res

        # Ensure any explicitly requested must-haves present in catalog are included in the plan
        user_musts = []
        raw_musts = session.get("must_haves") or ""
        if raw_musts:
            try:
                parsed_m = json.loads(raw_musts)
                if isinstance(parsed_m, list):
                    user_musts.extend([str(x) for x in parsed_m])
                elif isinstance(parsed_m, str):
                    user_musts.extend(re.split(r'[,;\n]|\band\b|\b\+\b|\b&\b', parsed_m))
            except Exception:
                user_musts.extend(re.split(r'[,;\n]|\band\b|\b\+\b|\b&\b', str(raw_musts)))

        if notes:
            user_musts.extend(re.split(r'[,;\n]|\band\b|\b\+\b|\b&\b', str(notes)))

        boq = res.get("boq", [])
        existing_cats = {it.get("category", "").lower() for it in boq}
        existing_ids = {it.get("item_id") for it in boq}
        added_any = False

        generic_skips = {"all", "everything", "standard", "any", "living room", "bedroom", "dining", "study", "yes", "yeah", "ok", "please", "room", "sofa", "furniture"}

        for req in user_musts:
            clean_req = re.sub(r'^(?:i want|i need|please add|give me|we want|looking for|also|with|a|an|the|some)\s+', '', req.strip(), flags=re.I).strip()
            if len(clean_req) < 3 or clean_req.lower() in generic_skips:
                continue

            # Check if this item exists in catalog for this room
            cat_found = self.catalog_agent.find_catalog_item_for_room(clean_req, room_type=room_type, style=style)
            if cat_found:
                c_cat = (cat_found.get("category") or "").lower()
                c_id = cat_found.get("item_id")
                if c_id not in existing_ids and c_cat not in existing_cats:
                    boq.append(self._create_boq_row(cat_found, preferred_style=style))
                    existing_cats.add(c_cat)
                    existing_ids.add(c_id)
                    added_any = True

        if added_any:
            res["boq"] = boq
            res = self._recalculate_plan_metrics(res, length_cm, width_cm, budget, style, room_type=room_type)

        return res

    def _create_boq_row(self, catalog_item: Dict[str, Any], preferred_style: str = "Scandinavian") -> Dict[str, Any]:
        """Formats a raw catalog DB row into a standardized 9-field BOQ entry."""
        w = catalog_item.get("width_cm")
        d = catalog_item.get("depth_cm")
        h = catalog_item.get("height_cm")
        dim_str = f"{w or 0} x {d or 0} x {h or 0} cm" if (w or d or h) else "Dimensions on site measurement"

        return {
            "item_id": catalog_item["item_id"],
            "category": catalog_item["category"],
            "name": catalog_item["name"],
            "style": catalog_item.get("style_tags") or preferred_style,
            "style_tags": catalog_item.get("style_tags") or preferred_style,
            "dimensions": dim_str,
            "width_cm": w,
            "depth_cm": d,
            "height_cm": h,
            "color_finish": catalog_item.get("color_finish") or "Natural finish",
            "finish": catalog_item.get("color_finish") or "Natural finish",
            "price_inr": catalog_item["price_inr"],
            "in_stock": catalog_item.get("in_stock", 1),
            "lead_time_days": catalog_item.get("lead_time_days", 7)
        }

    def _extract_remove_target(self, text: str) -> Optional[str]:
        """Extracts removal target keyword from various user removal phrasings."""
        m_why = re.search(
            r"\b(?:why is|why is there|why did you include|why do we have)\s+(?:a\s+|an\s+|the\s+)?([a-z0-9\s\-]+?)\s+(?:in|in the plan|here)",
            text,
            re.I
        )
        if m_why:
            return re.sub(r"[?.!,;]+$", "", m_why.group(1)).strip()

        m_rem = re.search(
            r"\b(?:remove|removing|delete|deleting|drop|dropping|take out|omit|omitting|get rid of|without|no longer need|don't want|dont want|do not want|no need for|cancel)\b\s*(?:a\s+|an\s+|the\s+|some\s+)?(.+)",
            text,
            re.I
        )
        if m_rem:
            return re.sub(r"[?.!,;]+$", "", m_rem.group(1)).strip()
        return None

    def _extract_add_target(self, text: str) -> Optional[str]:
        """Extracts addition target keyword from diverse user adding phrasings."""
        # 1. Why didn't you add / why are you not adding X
        m_why = re.search(
            r"\b(?:why are you not adding|why aren't you adding|why arent you adding|why didn't you add|why didnt you add|why haven't you added|why havent you added|why not add|why you didn't add|why you didnt add)\s+(?:a\s+|an\s+|the\s+)?(.+)",
            text,
            re.I
        )
        if m_why:
            return re.sub(r"[?.!,;]+$", "", m_why.group(1)).strip()

        # 2. I said add X / i asked to add X / i told to add X
        m_asked = re.search(
            r"\b(?:i said|i asked to|i told to|i want to|i'd like to|can we|could you|please|let's|also)\s+(?:add|include|put in|insert)\s+(?:a\s+|an\s+|the\s+|some\s+)?(.+)",
            text,
            re.I
        )
        if m_asked:
            return re.sub(r"[?.!,;]+$", "", m_asked.group(1)).strip()

        # 3. Direct add / adding / include / put in / insert
        m_add = re.search(
            r"\b(?:add|adding|include|including|put in|insert)\b\s*(?:a\s+|an\s+|the\s+|some\s+)?(.+)",
            text,
            re.I
        )
        if m_add:
            return re.sub(r"[?.!,;]+$", "", m_add.group(1)).strip()

        # 4. Want X / Need X
        m_want = re.search(
            r"\b(?:want|need|get)\s+(?:a\s+|an\s+|the\s+|some\s+)?(.+)",
            text,
            re.I
        )
        if m_want:
            return re.sub(r"[?.!,;]+$", "", m_want.group(1)).strip()

        return None

    def _find_and_remove_boq_item(
        self,
        boq: List[Dict[str, Any]],
        target_query: str
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """Finds and removes an item from boq matching target_query by category, name, or synonym."""
        cleaned = target_query.strip().lower()
        synonyms = {
            "arm chair": "armchair",
            "armchair": "armchair",
            "arm chairs": "armchair",
            "armchairs": "armchair",
            "chair": "armchair",
            "chairs": "armchair",
            "accent chair": "armchair",
            "accent chairs": "armchair",
            "lounge chair": "armchair",
            "lounge chairs": "armchair",
            "book shelf": "bookshelf",
            "book shelves": "bookshelf",
            "bookshelf": "bookshelf",
            "bookshelves": "bookshelf",
            "bookcase": "bookshelf",
            "book case": "bookshelf",
            "center table": "coffee table",
            "tea table": "coffee table",
            "coffee table": "coffee table",
            "coffeetable": "coffee table",
            "floor lamp": "floor lamp",
            "floorlamp": "floor lamp",
            "standing lamp": "floor lamp",
            "reading lamp": "table lamp",
            "table lamp": "table lamp",
            "lamp": "floor lamp",
            "lamps": "floor lamp",
            "light": "floor lamp",
            "lights": "floor lamp",
            "lighting": "floor lamp",
            "side table": "side table",
            "sidetable": "side table",
            "end table": "side table",
            "bean bag": "bean bag",
            "beanbag": "bean bag",
            "plant": "planter",
            "plants": "planter",
            "planter": "planter",
            "planters": "planter",
            "pots": "planter",
            "pot": "planter",
            "curtain": "curtains",
            "curtains": "curtains",
            "drapes": "curtains",
            "carpet": "rug",
            "carpets": "rug",
            "rug": "rug",
            "rugs": "rug",
            "couch": "sofa",
            "couches": "sofa",
            "sofa": "sofa",
            "sofas": "sofa",
            "closet": "wardrobe",
            "almirah": "wardrobe",
            "cupboard": "wardrobe",
            "wardrobe": "wardrobe",
            "painting": "wall art",
            "art": "wall art",
            "artwork": "wall art",
            "wall art": "wall art",
            "wallart": "wall art",
            "cushion": "cushions",
            "cushions": "cushions",
            "pillow": "cushions",
            "pillows": "cushions",
            "pouf": "ottoman",
            "pouffe": "ottoman",
            "ottoman": "ottoman",
            "tv": "tv unit",
            "television": "tv unit",
            "tv stand": "tv unit",
            "tv unit": "tv unit",
            "tv console": "tv unit",
            "media console": "tv unit"
        }
        mapped = synonyms.get(cleaned, cleaned)
        removed_item = None
        new_boq = []
        found = False

        def norm(s: str) -> str:
            return re.sub(r"[^a-z0-9]", "", (s or "").lower())

        norm_mapped = norm(mapped)
        norm_clean = norm(cleaned)
        norm_sing = re.sub(r"(ies|es|s)$", "", norm_mapped)

        for item in boq:
            if found:
                new_boq.append(item)
                continue
            cat = item.get("category") or ""
            name = item.get("name") or ""
            norm_cat = norm(cat)
            norm_name = norm(name)
            norm_cat_sing = re.sub(r"(ies|es|s)$", "", norm_cat)

            if (
                norm_mapped == norm_cat
                or norm_sing == norm_cat_sing
                or norm_clean == norm_cat
                or norm_mapped in norm_cat
                or (len(norm_cat) >= 4 and norm_cat in norm_mapped)
                or norm_mapped in norm_name
                or norm_clean in norm_name
                or (len(norm_name) >= 4 and norm_name in norm_mapped)
            ):
                removed_item = item
                found = True
            else:
                new_boq.append(item)

        return removed_item, new_boq

    def _recalculate_plan_metrics(
        self,
        plan: Dict[str, Any],
        length_cm: int,
        width_cm: int,
        budget_inr: int,
        style: str,
        room_type: str = "Living Room"
    ) -> Dict[str, Any]:
        """Recalculates financial summary, spatial fit, and one-liner recommendations for updated boq."""
        boq = plan.get("boq", [])
        selected_item_ids = [it["item_id"] for it in boq if it.get("item_id")]

        # Budget calculation
        calc_res = tools.budget_calculator(selected_item_ids, budget_inr, db_path=self.db_path)
        total_spent = calc_res["total_spent"]
        rem_budget = calc_res["remaining_budget"]
        utilization = round((total_spent / budget_inr * 100), 1) if budget_inr > 0 else 0.0

        # Layout fit calculation
        fit_res = tools.layout_fit_check(length_cm, width_cm, selected_item_ids, db_path=self.db_path)
        max_lead_days = max([x.get("lead_time_days", 7) for x in boq] or [7])
        rem_area_sqm = round(max(0.0, fit_res["room_area_sqm"] - fit_res["furniture_footprint_sqm"]), 2)
        rem_area_pct = round(max(0.0, (1.0 - fit_res.get("occupancy_ratio", 0.0)) * 100.0), 1)

        # Dynamic intelligent budget & styling recommendations in one-liner bullet points
        recs = {
            "budget_status": "UNDER" if rem_budget >= 0 else "EXCEEDED",
            "budget_difference_inr": abs(rem_budget),
            "max_lead_time_days": max_lead_days,
            "remaining_area_sqm": rem_area_sqm,
            "remaining_area_percentage": rem_area_pct
        }

        if rem_budget < 0:
            overage = abs(rem_budget)
            sorted_by_price = sorted(boq, key=lambda x: x.get("price_inr") or 0, reverse=True)
            top_item = sorted_by_price[0] if sorted_by_price else None
            top_name = top_item["name"] if top_item else "main seating"
            top_cat = top_item["category"] if top_item else "furniture"

            recs["item_recommendation"] = f"Remove or swap {top_cat} '{top_name}' to save ₹{min(overage, 25000):,} and balance your budget."
            recs["style_recommendation"] = f"Choose streamlined Minimalist profiles over handcrafted {style} pieces to reduce fabrication costs."
            recs["color_recommendation"] = "Opt for neutral woven fabrics with matte powder-coated finishes instead of expensive leather or brass."
            recs["summary_text"] = f"⚠️ Budget Exceeded by ₹{overage:,}! Remove or swap items to bring total spend under ₹{budget_inr:,}."
        else:
            surplus = rem_budget
            recs["item_recommendation"] = f"Add an accent armchair or hand-tufted wool rug using your remaining ₹{surplus:,} budget."
            recs["style_recommendation"] = f"Elevate the {style} theme by pairing warm walnut and oak finishes with ambient lighting."
            recs["color_recommendation"] = "Layer earthy terracotta, olive green, or soft indigo cushions over neutral upholstery."
            recs["summary_text"] = f"✅ Budget Under by ₹{surplus:,}! You have surplus budget to add accent seating or designer lighting."

        plan["boq"] = boq
        plan["financial_summary"] = {
            "budget_allocated_inr": budget_inr,
            "total_spent_inr": total_spent,
            "remaining_budget_inr": rem_budget,
            "budget_utilization_percentage": utilization,
            "max_lead_time_days": max_lead_days
        }
        plan["spatial_fit_summary"] = {
            "room_area_sqm": fit_res["room_area_sqm"],
            "furniture_footprint_sqm": fit_res["furniture_footprint_sqm"],
            "remaining_area_sqm": rem_area_sqm,
            "remaining_area_percentage": rem_area_pct,
            "occupancy_percentage": fit_res["occupancy_percentage"],
            "circulation_viable": fit_res["fits_circulation"]
        }
        plan["recommendations"] = recs
        return plan

    def _check_negative_guardrails(self, text: str) -> Optional[Tuple[str, str]]:
        """
        Negative Operational Guardrails Pre-flight Audit (Section 8).
        Strictly enforces operational boundaries and zero-tolerance gates:
        1. Confidentiality: No leaking system prompt, internal code, API keys, RAG, internal schema.
        2. Persona / Role Locking: Role-locked as interior designer Siya; no coding tasks, math solving, or persona hijacking.
        3. Civil / Structural Scope Refusal: Immediate refusal of load-bearing demolition, electrical rewiring, plumbing stacks.
        4. Neutrality: No commentary on personalities, communities, politics, cinema, countries.
        5. Domain Exclusivity: Strictly confined to interior design planning (refuses medical, legal, financial, cooking, etc.).
        """
        if not text:
            return None

        clean_lower = text.lower().strip()

        # -------------------------------------------------------------
        # 0. Inappropriate & Sexual Content Refusal Gate
        # -------------------------------------------------------------
        # Exclude legitimate interior design styling terms like 'nude color palette' or 'nude shades'
        has_nude_decor = bool(re.search(r"\b(nude\s+(color|palette|shade|tone|wall|paint|cushion|fabric|linen|finish|interior|aesthetic))\b", clean_lower))
        sexual_patterns = [
            r"\b(sex|sexual|sexy|nude|nudes|naked|nudity|porn|pornography|erotic|erotica|nsfw|fetish)\b",
            r"\b(send\s+(me\s+)?(nudes|sexy\s+pics|naked\s+photos)|show\s+(me\s+)?(your\s+)?(body|boobs|ass|tits))\b",
            r"\b(talk\s+dirty|dirty\s+talk|are\s+you\s+(horny|virgin)|want\s+to\s+have\s+sex|make\s+love)\b",
            r"\b(kiss\s+me|touch\s+(yourself|me)|sexual\s+(pleasure|fantas(y|ies)|act|desire))\b",
            r"\b(penis|vagina|boobs|breasts|genitals|masturbat(e|ion)|intercourse|orgasm)\b"
        ]
        if not has_nude_decor:
            for pattern in sexual_patterns:
                if re.search(pattern, clean_lower):
                    refusal_msg = (
                        "🛡️ Professional Decorum: As an AI Interior Design Consultant for Interior Company × Blocks, "
                        "I maintain strict professional boundaries and do not engage in sexual, romantic, or inappropriate conversations. "
                        "I am exclusively dedicated to interior space planning, furniture selections, and architectural aesthetics. "
                        "Please let me know how I may assist with your home design."
                    )
                    return ("SEXUAL_CONTENT_REFUSAL", refusal_msg)

        # -------------------------------------------------------------
        # 1. IP & Confidentiality Gate (Guardrail 8 / Rule 3)
        # -------------------------------------------------------------
        # Checks for attempts to dump system prompt, source code, API keys, RAG architecture, internal credentials
        prompt_leak_patterns = [
            r"\b(system\s+prompt|developer\s+prompt|initial\s+prompt|hidden\s+prompt|base\s+prompt)\b",
            r"\b(show|reveal|print|tell|display|give|share|dump|leak)\s+(me\s+)?(your\s+)?(prompt|system\s+instructions|instructions\s+above|rules|developer\s+instructions)\b",
            r"\b(repeat|output)\s+(the\s+)?(above|previous)\s+(text|prompt|instructions)\b",
            r"\b(ignore\s+all\s+previous\s+instructions)\b",
            r"\b(api\s*key|secret\s*key|auth\s*token|credentials|openai_api_key|gemini_api_key|private\s*key)\b",
            r"\b(core\s+code|source\s+code|backend\s+code|python\s+code\s+of|github\s+repo|codebase)\b",
            r"\b(rag\s+architecture|rag\s+pipeline|embedding\s+model|vector\s+database|vector\s+store|sqlite\s+schema|db\s+schema|internal\s+tools?\s+code)\b",
            r"\b(api\s+documentation|swagger|openapi\s+spec|postman\s+collection)\b"
        ]
        for pattern in prompt_leak_patterns:
            if re.search(pattern, clean_lower):
                refusal_msg = (
                    "🔒 Guardrail Alert: I cannot disclose internal core code, proprietary system prompts, "
                    "API documentation, API keys, RAG architecture, or database schemas. All internal configurations "
                    "and operational instructions are strictly confidential. I am delighted to assist you with your interior design planning!"
                )
                return ("CONFIDENTIALITY_BREACH", refusal_msg)

        # -------------------------------------------------------------
        # 2. Persona Locking & Roleplay / Coding Refusal (Guardrail 7 / Rule 2)
        # -------------------------------------------------------------
        # Checks for coding tasks, writing software, debugging, non-design roleplay, persona hijacking
        coding_patterns = [
            r"\b(write|create|generate|debug|fix)\s+(a\s+)?(python|javascript|java|c\+\+|html|css|sql|rust|go|php|typescript|bash|shell|powershell)\s+(script|code|function|program|app|query)\b",
            r"\b(write|give\s+me)\s+(some\s+)?(code|script|algorithm|regex|sql\s+query|stored\s+procedure)\b",
            r"\b(solve\s+this\s+(coding|programming)\s+(problem|bug|issue))\b",
            r"\b(npm\s+install|pip\s+install|git\s+clone|docker\s+run)\b",
            r"\b(write\s+a\s+react\s+component|vue\s+component|flutter\s+widget)\b"
        ]
        for pattern in coding_patterns:
            if re.search(pattern, clean_lower):
                refusal_msg = (
                    "🤖 Role-Lock Enforced: I am Siya, your dedicated AI Interior Design Consultant for Interior Company × Blocks. "
                    "I am strictly role-locked to interior design planning and do not write code, debug software, or perform programming tasks. "
                    "Please let me know your room type and dimensions so we can create your interior space plan!"
                )
                return ("ROLE_HIJACK_REFUSAL", refusal_msg)

        roleplay_patterns = [
            r"\b(act\s+as|pretend\s+to\s+be|you\s+are\s+now|roleplay\s+as|simulate|jailbreak|dan\s+mode)\b",
            r"\b(forget\s+(that\s+)?you\s+are\s+(an\s+)?interior\s+design(er)?)\b",
            r"\b(be\s+my\s+(therapist|doctor|lawyer|teacher|tutor|accountant|girlfriend|boyfriend|astrologer))\b",
            r"\b(write\s+(an\s+)?(essay|story|poem|song|rap|fanfiction))\b",
            r"\b(solve\s+(the\s+)?(equation|math\s+problem|calculus|algebra|integral))\b"
        ]
        for pattern in roleplay_patterns:
            if re.search(pattern, clean_lower):
                refusal_msg = (
                    "🎭 Role-Lock Enforced: I am Siya, your dedicated AI Interior Design Consultant. "
                    "I strictly operate within my assigned persona and cannot adopt alternate roles, roleplay, or perform tasks outside interior space planning. "
                    "Let's focus on your home: which room would you like to design today?"
                )
                return ("ROLE_HIJACK_REFUSAL", refusal_msg)

        # -------------------------------------------------------------
        # 3. Civil, Structural & Electrical Safety Scope Refusal (Guardrail 3)
        # -------------------------------------------------------------
        civil_patterns = [
            r"\b(knock\s+down|demolish|break|remove|tear\s+down|cut)\s+(the\s+)?(load[\s-]bearing|rcc|structural|exterior)?\s*(wall|beam|pillar|column|slab)\b",
            r"\b(load[\s-]bearing\s+wall|rcc\s+column|structural\s+beam|structural\s+alteration)\b",
            r"\b(core\s+drilling|chisel\s+concrete|alter\s+foundation)\b",
            r"\b(220v|440v|breaker\s+box|electrical\s+conduit|main\s+panel|fuse\s+box|rewir(e|ing))\s*(splic|alter|mod)\b",
            r"\b(relocate|move)\s+(main\s+)?(sewage\s+stack|gas\s+line|soil\s+pipe|plumbing\s+shaft)\b"
        ]
        for pattern in civil_patterns:
            if re.search(pattern, clean_lower):
                refusal_msg = (
                    "⚠️ Safety Guardrail: I cannot assist with civil, structural, electrical, or plumbing alterations "
                    "such as modifying load-bearing walls, breaking RCC pillars, or rewiring mains conduits. "
                    "Please consult a certified civil engineer or licensed structural contractor for life-safety assessments. "
                    "I can gladly assist with non-structural furniture layouts, finishes, and decor!"
                )
                return ("CIVIL_SCOPE_REFUSAL", refusal_msg)

        # -------------------------------------------------------------
        # 4. Socio-Political & Cultural Neutrality (Guardrail 6 / Rule 1)
        # "Do not comment on any personality, community, politics, cinema, country."
        # -------------------------------------------------------------
        # Exclude legitimate interior design terms like "home cinema room" or "country style"
        has_cinema_room = bool(re.search(r"\b(home\s+cinema|cinema\s+room|movie\s+room|media\s+room|theatre\s+room)\b", clean_lower))
        has_country_style = bool(re.search(r"\b(country\s+(style|aesthetic|theme|decor|cottage|modern|french))\b", clean_lower))

        neutrality_patterns = [
            # Politics & Politicians
            r"\b(modi|narendra\s+modi|rahul\s+gandhi|trump|donald\s+trump|biden|joe\s+biden|putin|zelensky)\b",
            r"\b(bjp|congress\s+party|aap|aam\s+aadmi|democrat(s|ic)?|republican(s)?|parliament|lok\s+sabha|rajya\s+sabha)\b",
            r"\b(who\s+to\s+vote|election\s+(opinion|winner|result)|political\s+(party|view|agenda|opinion)|politics)\b",
            r"\b(communism|fascism|socialism|authoritarianism|left[\s-]wing|right[\s-]wing)\b",
            
            # Communities, Caste & Religious controversies
            r"\b(hindu(ism)?|muslim(s)?|islam(ic)?|christian(ity)?|sikh(ism)?|jewish|judaism)\s+(is|are|versus|vs|better|worse|bad|good)\b",
            r"\b(caste\s+system|brahmin|dalit|kshatriya|vaishya|reservation\s+policy|communal\s+riot|communalism)\b",
            r"\b(which\s+(religion|community|caste)\s+is\s+(better|best|superior|worst))\b",
            
            # Personalities & Celebrities (outside interior design context)
            r"\b(what\s+do\s+you\s+think\s+of|opinion\s+on)\s+([a-z]+)\b",
            r"\b(shah\s*rukh\s*khan|salman\s*khan|aamir\s*khan|deepika|katrina|alia\s+bhatt|virat\s+kohli|rohit\s+sharma|dhoni|celebrity\s+gossip)\b",
            r"\b(is\s+[a-z\s]+\s+(a\s+good\s+person|corrupt|evil|hero))\b",
            
            # Cinema & Film Critique / Gossip (excluding home cinema rooms)
            r"\b(movie\s+review|box\s+office\s+collection|bollywood\s+(is|gossip|stars)|hollywood\s+(gossip|scandal)|film\s+industry\s+critique)\b",
            r"\b(rate\s+the\s+movie|is\s+the\s+film\s+[a-z\s]+\s+good|best\s+actor\s+in|worst\s+actor)\b",
            
            # Country & Geopolitical disputes (excluding country style decor)
            r"\b(india\s+vs\s+pakistan|israel\s+vs\s+palestine|russia\s+vs\s+ukraine|china\s+vs\s+taiwan|geopolitical\s+conflict)\b",
            r"\b(which\s+country\s+is\s+(better|best|worst|corrupt))\b",
            r"\b(patriotism|boycott\s+[a-z]+|hate\s+[a-z]+)\b"
        ]

        if not has_cinema_room and not has_country_style:
            for pattern in neutrality_patterns:
                if re.search(pattern, clean_lower):
                    refusal_msg = (
                        "🕊️ Neutrality Policy: As an AI Interior Design Consultant, I strictly maintain operational neutrality "
                        "and do not comment on personalities, communities, politics, cinema, or countries. "
                        "I am exclusively here to help you style and optimize your interior living spaces! How can I assist with your room?"
                    )
                    return ("NEUTRALITY_BREACH", refusal_msg)

        # -------------------------------------------------------------
        # 5. Domain Boundary & Interior Exclusivity Gate (Guardrail 9 / Rule 4)
        # "Do not go beyond the field of interior design planning."
        # -------------------------------------------------------------
        out_of_domain_patterns = [
            # Medical / Health
            r"\b(medical\s+advice|symptom(s)?\s+of|cure\s+for|medicine\s+for|dosage\s+of|diagnose\s+me|paracetamol|antibiotics)\b",
            r"\b(how\s+to\s+treat\s+(fever|cough|cancer|infection|diabetes|headache))\b",
            
            # Legal
            r"\b(legal\s+advice|sue\s+my|file\s+a\s+lawsuit|court\s+case|legal\s+notice|draft\s+a\s+contract|tenant\s+rights\s+lawyer)\b",
            
            # Financial, Stocks & Crypto
            r"\b(stock\s+tips|buy\s+or\s+sell\s+stocks|crypto\s+investment|bitcoin\s+prediction|ethereum|forex\s+trading|best\s+mutual\s+funds)\b",
            
            # Automotive & Heavy Engineering
            r"\b(repair\s+my\s+car|change\s+(engine\s+)?oil|fix\s+(car|bike)\s+brakes|spark\s+plug|transmission\s+repair)\b",
            
            # Cooking Recipes
            r"\b(recipe\s+for|how\s+to\s+cook|ingredients\s+to\s+bake|how\s+to\s+make\s+(biryani|pasta|curry|pizza|cake))\b"
        ]
        for pattern in out_of_domain_patterns:
            if re.search(pattern, clean_lower):
                refusal_msg = (
                    "📐 Domain Boundary: My capabilities are strictly specialized in the field of interior design planning, "
                    "spatial ergonomics, furniture selections, color palettes, and furnishing budgeting. "
                    "I cannot assist with queries outside interior design. Let's design your room space together!"
                )
                return ("OUT_OF_DOMAIN_REFUSAL", refusal_msg)

        return None
