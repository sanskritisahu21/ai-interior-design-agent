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

def run_flow_test(name: str, turns: list):
    agent = ConversationAgent()
    session_id = f"test-{uuid.uuid4().hex[:8]}"

    print("\n" + "=" * 80)
    print(f"TEST: {name} (Session: {session_id})")
    print("=" * 80)

    init_msg = agent.get_initial_greeting(session_id)
    print(f"🤖 SIYA (Initial): {init_msg['message']}")

    for turn in turns:
        res = agent.process_message(session_id, turn)
        print(f"👤 USER: {turn}")
        print(f"🤖 SIYA: {res['message']}")
        print(f"   [Stage]: {res['metadata'].get('stage')}")

    sess = db.get_or_create_session(session_id)
    print(f"✅ FINAL SESSION: L={sess.get('length_cm')}, W={sess.get('width_cm')}, H={sess.get('height_cm')}, Stage={sess.get('stage')}")
    return sess

def test_all_flows():
    # 1. User gives 200 290 310 in one go
    s1 = run_flow_test("3 Numbers In One Go (200 290 310)", [
        "Hii",
        "Living room",
        "200 290 310"
    ])
    assert s1.get("length_cm") == 200
    assert s1.get("width_cm") == 290
    assert s1.get("height_cm") == 310
    assert s1.get("stage") == "BUDGET"

    # 2. User gives 200 210 (L & B), then 200 only (H)
    s2 = run_flow_test("2 Numbers (200 210) then 1 Number (200) for Height", [
        "Hi",
        "Bedroom",
        "200 210",
        "200"
    ])
    assert s2.get("length_cm") == 200
    assert s2.get("width_cm") == 210
    assert s2.get("height_cm") == 200
    assert s2.get("stage") == "BUDGET"

    # 3. User gives labeled dimensions in one go: length is 200, breadth is 210 and height is 300
    s3 = run_flow_test("Labeled Dimensions In One Go", [
        "Hi",
        "Living room",
        "length is 200, breadth is 210 and height is 300"
    ])
    assert s3.get("length_cm") == 200
    assert s3.get("width_cm") == 210
    assert s3.get("height_cm") == 300
    assert s3.get("stage") == "BUDGET"

    # 4. User gives out-of-order labeled dimensions: height is 300, length is 200, breadth is 210
    s4 = run_flow_test("Out-of-order Labeled Dimensions", [
        "Hi",
        "Dining room",
        "height is 300, length is 200, breadth is 210"
    ])
    assert s4.get("length_cm") == 200
    assert s4.get("width_cm") == 210
    assert s4.get("height_cm") == 300
    assert s4.get("stage") == "BUDGET"

    # 5. User gives 200 210 310 in one go
    s5 = run_flow_test("3 Numbers (200 210 310)", [
        "Hii",
        "Living room",
        "200 210 310"
    ])
    assert s5.get("length_cm") == 200
    assert s5.get("width_cm") == 210
    assert s5.get("height_cm") == 310
    assert s5.get("stage") == "BUDGET"

    print("\n🎉 ALL 5 CONVERSATION FLOW TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all_flows()
