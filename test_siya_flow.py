import sys
import uuid
from agents import ConversationAgent
import db

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def test_full_flow():
    agent = ConversationAgent()
    session_id = f"test-{uuid.uuid4().hex[:8]}"

    turns = [
        "Hii",
        "I am confused",
        "Living room",
        "I don't know",
        "15 * 12 feet",
        "I don't have a budget",
        "Cyberpunk style",
        "Scandinavian",
        "Togo sofa, coffee table, rug"
    ]

    print("=" * 80)
    print(f"TESTING SIYA CONVERSATION FLOW (Session: {session_id})")
    print("=" * 80)

    # 1. Proactive opening greeting from Siya
    init_msg = agent.get_initial_greeting(session_id)
    print(f"🤖 SIYA (Initial Message): {init_msg['message']}")
    print("-" * 80)

    for turn in turns:
        res = agent.process_message(session_id, turn)
        print(f"👤 USER: {turn}")
        print(f"🤖 SIYA: {res['message']}")
        print(f"   [Chips]: {res['metadata'].get('chips', [])}")
        print("-" * 80)

    # Verify session persisted in SQLite
    sess = db.get_or_create_session(session_id)
    print("\nVERIFYING SQLITE PERSISTENCE:")
    print(f"• Room Type: {sess.get('room_type')}")
    print(f"• Dimensions: {sess.get('length_cm')} x {sess.get('width_cm')} x {sess.get('height_cm')} cm")
    print(f"• Style: {sess.get('style')}")
    print(f"• Stage: {sess.get('stage')}")
    print(f"• Has Current Plan: {bool(sess.get('current_plan_json'))}")

    history = db.get_chat_history(session_id)
    print(f"• Messages Stored in SQLite: {len(history)} messages logged")
    print("=" * 80)

if __name__ == "__main__":
    test_full_flow()
