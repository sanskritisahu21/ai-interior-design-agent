import uuid
from agents import ConversationAgent
import json

agent = ConversationAgent()
sid = f"test-edit-{uuid.uuid4().hex[:8]}"

agent.get_initial_greeting(sid)
agent.process_message(sid, "Living room")
agent.process_message(sid, "200 290 310")
agent.process_message(sid, "200000")
agent.process_message(sid, "Scandinavian")
res_init = agent.process_message(sid, "sofa, coffee table, TV unit, floor lamp")

plan0 = res_init["metadata"]["plan"]
print("Initial Items:", [x["name"] for x in plan0["boq"]])
print("Initial Spend:", plan0["financial_summary"]["total_spent_inr"])

# 1. Test ADD armchair (item in catalog)
res_add = agent.process_message(sid, "can we add an armchair")
print("\n--- ADD ARMCHAIR ---")
print("Msg:", res_add["message"])
plan_add = res_add["metadata"].get("plan")
if plan_add:
    print("New Items:", [x["name"] for x in plan_add["boq"]])
    print("New Spend:", plan_add["financial_summary"]["total_spent_inr"])

# 2. Test ADD unavailable item (jacuzzi)
res_unavail = agent.process_message(sid, "please add a jacuzzi")
print("\n--- ADD UNAVAILABLE ---")
print("Msg:", res_unavail["message"])

# 3. Test REMOVE coffee table
res_rem = agent.process_message(sid, "remove coffee table")
print("\n--- REMOVE COFFEE TABLE ---")
print("Msg:", res_rem["message"])
plan_rem = res_rem["metadata"].get("plan")
if plan_rem:
    print("New Items:", [x["name"] for x in plan_rem["boq"]])
    print("New Spend:", plan_rem["financial_summary"]["total_spent_inr"])

