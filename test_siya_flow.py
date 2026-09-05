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

    # 6. Complete End-to-End Flow Through Must-Haves (9 Columns, End Metrics, Recommendations)
    agent = ConversationAgent()
    sid = f"test-full-{uuid.uuid4().hex[:8]}"
    agent.get_initial_greeting(sid)
    agent.process_message(sid, "Living room")
    agent.process_message(sid, "200 290 310")
    agent.process_message(sid, "200000")
    agent.process_message(sid, "Scandinavian")
    res = agent.process_message(sid, "sofa, coffee table, TV unit, rug, floor lamp")

    plan = res["metadata"].get("plan")
    assert plan is not None, "Plan must not be None after must-haves"
    boq = plan.get("boq", [])
    assert len(boq) > 0, "BOQ items must be generated"

    # Verify all 9 requested table fields are present on every row
    for item in boq:
        assert "category" in item, "Item must have category (items)"
        assert "name" in item, "Item must have name (in catalog table)"
        assert "style" in item or "style_tags" in item, "Item must have style"
        assert "price_inr" in item, "Item must have price"
        assert "width_cm" in item, "Item must have width"
        assert "depth_cm" in item, "Item must have depth"
        assert "height_cm" in item, "Item must have height"
        assert "color_finish" in item or "finish" in item, "Item must have color"
        assert "lead_time_days" in item, "Item must have days required"

    # Verify end metrics: total cost, days required, remaining area of room
    fin = plan.get("financial_summary", {})
    spat = plan.get("spatial_fit_summary", {})
    recs = plan.get("recommendations", {})

    assert "total_spent_inr" in fin, "Must have total cost"
    assert "max_lead_time_days" in fin or "max_lead_time_days" in recs, "Must have days required"
    assert "remaining_area_sqm" in spat or "remaining_area_sqm" in recs, "Must have remaining area of room"

    # Verify recommendations for changes: items, style, color, budget under/exceed
    assert "item_recommendation" in recs, "Must have item recommendation"
    assert "style_recommendation" in recs, "Must have style recommendation"
    assert "color_recommendation" in recs, "Must have color recommendation"
    assert "budget_status" in recs, "Must have budget status (UNDER or EXCEEDED)"
    print("\n✅ FLOW 6: Full Must-Haves Plan Generation with 9 fields, end metrics, and recommendations PASSED!")

    # 7. Unavailable Must-Haves Reporting Test (User example: sofa, coffee table, TV, Floor Lamp, carpet, soft lighting, cupboard)
    agent = ConversationAgent()
    sid = f"test-unavail-{uuid.uuid4().hex[:8]}"
    agent.get_initial_greeting(sid)
    agent.process_message(sid, "Living room")
    agent.process_message(sid, "200 290 310")
    agent.process_message(sid, "200000")
    agent.process_message(sid, "Mid-Century")
    res7 = agent.process_message(sid, "sofa, coffee table, TV, Floor Lamp, carpet, soft lighting, cupboard")

    msg = res7["message"]
    print("\n[Flow 7 Response Message]:\n" + msg)

    # Verify unavailable items are explicitly reported to user
    assert "We don't have" in msg, "Must explicitly tell user we don't have missing items"
    assert "carpet" in msg.lower(), "Must mention carpet is not available"
    assert "soft lighting" in msg.lower(), "Must mention soft lighting is not available"
    assert "cupboard" in msg.lower(), "Must mention cupboard is not available"
    assert "available items" in msg.lower(), "Must mention available items"
    assert "Sofa" in msg and "Coffee Table" in msg, "Must list included items"

    # Verify plan summary is removed from chat message
    assert "PLAN SUMMARY" not in msg, "Plan summary must be removed from chat text"
    assert "Total Cost:" not in msg, "Redundant Total Cost line must be removed from chat text"

    # Verify recommendations are present as one-liner bullet points
    assert "💡 Recommendations:" in msg, "Must have Recommendations section"
    assert "• Items:" in msg, "Must have Items bullet point"
    assert "• Style:" in msg, "Must have Style bullet point"
    assert "• Color & Finish:" in msg, "Must have Color & Finish bullet point"

    print("\n✅ FLOW 7: Unavailable Must-Haves Reporting & Concise Recommendations PASSED!")

    # 8. Dynamic Plan Modification: Adding arbitrary items, missing items alert, removing arbitrary items, and plan recreation
    agent = ConversationAgent()
    sid8 = f"test-modify-{uuid.uuid4().hex[:8]}"
    agent.get_initial_greeting(sid8)
    agent.process_message(sid8, "Living room")
    agent.process_message(sid8, "400 350 280")
    agent.process_message(sid8, "250000")
    agent.process_message(sid8, "Scandinavian")
    res8_init = agent.process_message(sid8, "sofa, coffee table, TV unit")

    plan8_init = res8_init["metadata"].get("plan")
    assert plan8_init is not None, "Initial plan must be present"
    init_spend = plan8_init["financial_summary"]["total_spent_inr"]
    init_items = [it["name"] for it in plan8_init["boq"]]
    init_cats = [it["category"] for it in plan8_init["boq"]]
    print(f"\n[Flow 8 Initial]: Spend=₹{init_spend:,}, Items={init_items}")

    # Case A: User asks to add an item that is NOT in recommendation (e.g. Bookshelf)
    res8_add = agent.process_message(sid8, "can we add a bookshelf")
    plan8_add = res8_add["metadata"].get("plan")
    assert plan8_add is not None, "Plan must be returned after add"
    add_spend = plan8_add["financial_summary"]["total_spent_inr"]
    add_cats = [it["category"] for it in plan8_add["boq"]]
    assert "Bookshelf" in add_cats, "Bookshelf must be added to BOQ"
    assert add_spend > init_spend, f"Spend must increase after adding bookshelf ({add_spend} > {init_spend})"
    assert "✅ Added" in res8_add["message"], "Must confirm addition of item"
    print(f"[Flow 8 Add Bookshelf]: Spend=₹{add_spend:,}, Categories={add_cats}")

    # Case B: User asks to add an item NOT in the catalog (e.g. jacuzzi)
    res8_unavail = agent.process_message(sid8, "add a jacuzzi")
    assert "We don't have 'jacuzzi' in our catalog for Living Room" in res8_unavail["message"], "Must alert that item is not available"
    assert "available categories for Living Room" in res8_unavail["message"], "Must suggest available categories"
    # Verify plan wasn't corrupted
    assert len(res8_unavail["metadata"]["plan"]["boq"]) == len(plan8_add["boq"]), "BOQ count must remain unchanged on unavailable add"
    print(f"[Flow 8 Add Unavailable Jacuzzi]: Correctly alerted unavailable!")

    # Case C: User asks to remove an item (e.g. Coffee Table)
    res8_rem = agent.process_message(sid8, "please remove the coffee table")
    plan8_rem = res8_rem["metadata"].get("plan")
    assert plan8_rem is not None, "Plan must be returned after remove"
    rem_spend = plan8_rem["financial_summary"]["total_spent_inr"]
    rem_cats = [it["category"] for it in plan8_rem["boq"]]
    assert "Coffee Table" not in rem_cats, "Coffee Table must be removed from BOQ"
    assert rem_spend < add_spend, f"Spend must decrease after removing coffee table ({rem_spend} < {add_spend})"
    assert "🗑️ Removed" in res8_rem["message"], "Must confirm item removal"
    print(f"[Flow 8 Remove Coffee Table]: Spend=₹{rem_spend:,}, Categories={rem_cats}")

    # Case D: User asks to remove an item not in the plan
    res8_rem_missing = agent.process_message(sid8, "remove dining table")
    assert "was not found in your current design plan" in res8_rem_missing["message"], "Must inform user item was not in plan"
    print(f"[Flow 8 Remove Non-existent Item]: Correctly notified not found!")

    # Case E: Over-budget scenario where user removes an item of their choice
    sid8_over = f"test-over-{uuid.uuid4().hex[:8]}"
    agent.get_initial_greeting(sid8_over)
    agent.process_message(sid8_over, "Living room")
    agent.process_message(sid8_over, "400 350 280")
    agent.process_message(sid8_over, "60000")  # Tight budget
    agent.process_message(sid8_over, "Scandinavian")
    res_over = agent.process_message(sid8_over, "sofa, coffee table, TV unit, armchair")
    plan_over = res_over["metadata"].get("plan")
    # Add an item to deliberately exceed budget if not already exceeded
    agent.process_message(sid8_over, "add floor lamp")
    res_exceeded = agent.process_message(sid8_over, "add bookshelf")
    plan_exceeded = res_exceeded["metadata"].get("plan")
    spend_exceeded = plan_exceeded["financial_summary"]["total_spent_inr"]
    rem_b_exceeded = plan_exceeded["financial_summary"]["remaining_budget_inr"]
    print(f"[Flow 8 Over Budget]: Total spend=₹{spend_exceeded:,}, Remaining=₹{rem_b_exceeded:,}")

    # User removes an item of their choice (not necessarily what was recommended)
    res_user_choice = agent.process_message(sid8_over, "remove sofa")
    plan_user_choice = res_user_choice["metadata"].get("plan")
    user_choice_cats = [it["category"] for it in plan_user_choice["boq"]]
    assert "Sofa" not in user_choice_cats, "Sofa must be removed as requested by user"
    assert plan_user_choice["financial_summary"]["total_spent_inr"] < spend_exceeded, "Spend must decrease"
    print(f"[Flow 8 Over Budget User Removes Choice]: Sofa removed! New spend=₹{plan_user_choice['financial_summary']['total_spent_inr']:,}")

    print("\n✅ FLOW 8: Dynamic Plan Modifications (Arbitrary Add/Remove, Catalog Checking, Plan Recreation) PASSED!")

    # 9. Test Exact Armchair Resolution and Plan Recreation (User issue: "add arm chair")
    agent = ConversationAgent()
    sid9 = f"test-armchair-{uuid.uuid4().hex[:8]}"
    agent.get_initial_greeting(sid9)
    agent.process_message(sid9, "Living room")
    agent.process_message(sid9, "200 290 310")
    agent.process_message(sid9, "200000")
    agent.process_message(sid9, "Mid-Century")
    res9_init = agent.process_message(sid9, "sofa, coffee table, TV, Floor Lamp")

    plan9_init = res9_init["metadata"].get("plan")
    assert plan9_init is not None, "Initial plan must be present"
    init_items = [it["name"] for it in plan9_init["boq"]]
    init_cats = [it["category"] for it in plan9_init["boq"]]
    init_cost = plan9_init["financial_summary"]["total_spent_inr"]
    init_area = plan9_init["spatial_fit_summary"]["remaining_area_sqm"]

    print(f"\n[Flow 9 Initial]: Items={init_cats}, Cost=₹{init_cost:,}, Free Area={init_area} sqm")
    assert "Armchair" not in init_cats, "Armchair should not be in initial plan"

    # Step A: User says "add arm chair" (with space - exactly what previously failed)
    res9_add = agent.process_message(sid9, "add arm chair")
    plan9_add = res9_add["metadata"].get("plan")
    assert plan9_add is not None, "Plan must be recreated after adding arm chair"
    add_cats = [it["category"] for it in plan9_add["boq"]]
    add_cost = plan9_add["financial_summary"]["total_spent_inr"]
    add_area = plan9_add["spatial_fit_summary"]["remaining_area_sqm"]

    print(f"[Flow 9 After 'add arm chair']: Items={add_cats}, Cost=₹{add_cost:,}, Free Area={add_area} sqm")
    assert "Armchair" in add_cats, "Armchair must be added to the new plan"
    assert len(plan9_add["boq"]) == len(plan9_init["boq"]) + 1, "BOQ must have +1 item"
    assert add_cost > init_cost, f"Total cost must increase ({add_cost} > {init_cost})"
    assert add_area < init_area, f"Remaining room area must decrease ({add_area} < {init_area})"

    # Step B: User says "remove coffee table"
    res9_rem = agent.process_message(sid9, "remove coffee table")
    plan9_rem = res9_rem["metadata"].get("plan")
    assert plan9_rem is not None, "Plan must be recreated after removing coffee table"
    rem_cats = [it["category"] for it in plan9_rem["boq"]]
    rem_cost = plan9_rem["financial_summary"]["total_spent_inr"]
    rem_area = plan9_rem["spatial_fit_summary"]["remaining_area_sqm"]

    print(f"[Flow 9 After 'remove coffee table']: Items={rem_cats}, Cost=₹{rem_cost:,}, Free Area={rem_area} sqm")
    assert "Coffee Table" not in rem_cats, "Coffee table must be removed from new plan"
    assert "Armchair" in rem_cats, "Armchair must still be preserved in the plan"
    assert rem_cost < add_cost, f"Total cost must decrease after removal ({rem_cost} < {add_cost})"
    assert rem_area > add_area, f"Remaining area must increase after removal ({rem_area} > {add_area})"

    # Step C: Conversational inquiry: "why are you not adding armchair?" in fresh session
    sid9_c = f"test-inquiry-{uuid.uuid4().hex[:8]}"
    agent.get_initial_greeting(sid9_c)
    agent.process_message(sid9_c, "Living room")
    agent.process_message(sid9_c, "200 290 310")
    agent.process_message(sid9_c, "200000")
    agent.process_message(sid9_c, "Mid-Century")
    agent.process_message(sid9_c, "sofa, coffee table, TV")
    res9_why = agent.process_message(sid9_c, "why are you not adding armchair?")
    plan9_why = res9_why["metadata"].get("plan")
    assert plan9_why is not None, "Plan must be recreated on 'why are you not adding armchair?'"
    why_cats = [it["category"] for it in plan9_why["boq"]]
    assert "Armchair" in why_cats, "Armchair must be added upon 'why are you not adding armchair?'"
    print(f"[Flow 9 Inquiry 'why are you not adding armchair?']: Correctly added Armchair: {why_cats}")

    print("\n✅ FLOW 9: Armchair Addition ('arm chair', 'armchair') & Plan Recreation PASSED!")

    print("\n🎉 ALL 9 CONVERSATION FLOW TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all_flows()

