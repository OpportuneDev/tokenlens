"""
demo_bad.py — A multi-turn medical chatbot with common token waste patterns.

Shows how efficiency degrades turn by turn as:
- History grows unbounded
- System prompt is never cached
- Tool definitions are loaded in full every call
- Error bodies accumulate in context

Run with: python examples/demo_bad.py
No API key needed — uses analyse() directly to simulate calls.
"""

from token_lens import analyse

SYSTEM_PROMPT = """You are a clinical decision support assistant for doctors.
You have deep knowledge of fertility, ENT, and cosmetic surgery specialties.
Always follow safety protocols: never silently assign a document to a patient.
Confirm every assignment. If there is a mismatch between document content and
patient name on record, stop and ask. Maintain the speed of the doctor's thinking.
Never go silent during processing. Send proactive updates for any step over 5s.
You must be concise, precise, and evidence-based. Cite guidelines where relevant.
Do not hallucinate drug doses or diagnostic criteria. When uncertain, say so.
""" + ("Additional clinical context. " * 30)  # simulates a realistic long prompt

TOOLS = [
    {"name": "get_patient_summary",  "description": "Get full patient summary",        "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}}},
    {"name": "get_lab_results",      "description": "Get lab results for a patient",   "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}, "test": {"type": "string"}}}},
    {"name": "get_visit_notes",      "description": "Retrieve visit notes",            "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}}},
    {"name": "get_medications",      "description": "Get current medications",         "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}}},
    {"name": "get_imaging_reports",  "description": "Retrieve imaging reports",        "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}}},
    {"name": "search_guidelines",    "description": "Search clinical guidelines",      "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}},
    {"name": "create_referral",      "description": "Create a specialist referral",    "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}}},
    {"name": "schedule_followup",    "description": "Schedule a follow-up appointment","input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}}},
    {"name": "send_report",          "description": "Send report to patient",          "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}}},
    {"name": "get_risk_score",       "description": "Calculate patient risk score",    "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}}},
]

# Simulated conversation turns
TURNS = [
    ("user", "Show me Priya Sharma's latest lab results."),
    ("assistant", "Here are Priya Sharma's latest results: FSH 8.2 mIU/mL (Day 3), AMH 1.4 ng/mL, LH 5.1 mIU/mL. All within acceptable ranges for her age."),
    ("user", "What was her AMH last cycle?"),
    ("assistant", "Previous cycle AMH was 1.6 ng/mL. There's a slight downward trend worth monitoring."),
    ("user", "Error: 500 Internal Server Error\nTraceback (most recent call last):\n  File 'processor.py', line 142, in get_guidelines\nKeyError: 'specialty'\nFailed to retrieve ESHRE guidelines."),
    ("assistant", "I encountered an error retrieving the guidelines. Let me retry."),
    ("user", "Error: 500 Internal Server Error\nTraceback (most recent call last):\n  File 'processor.py', line 142, in get_guidelines\nKeyError: 'specialty'\nFailed to retrieve ESHRE guidelines."),
    ("assistant", "Still encountering errors. The guidelines service may be down."),
    ("user", "Ok skip that. What does her AMH trend suggest?"),
    ("assistant", "A decline from 1.6 to 1.4 ng/mL over one cycle may indicate early diminished ovarian reserve. Recommend repeat testing in 3 months."),
    ("user", "What's the recommended next step per ESHRE?"),
]

print("\n" + "="*60)
print("  DEMO: Bad version — all waste patterns active")
print("="*60)

history = []
for i, (role, content) in enumerate(TURNS):
    if role == "assistant":
        history.append({"role": "assistant", "content": content})
        continue

    history.append({"role": "user", "content": content})

    request = {
        "model": "claude-sonnet-4-6",
        "system": SYSTEM_PROMPT,    # no cache_control
        "messages": history[:-1],   # full unbounded history
        "tools": TOOLS,             # all 10 tools every call
        "max_tokens": 1024,
    }

    user_turn = sum(1 for m in history if m["role"] == "user")
    print(f"\n{'─'*60}")
    print(f"  Turn {user_turn}: \"{content[:55]}{'...' if len(content)>55 else ''}\"")
    print(f"{'─'*60}")

    analyse(request, output_tokens=180)
