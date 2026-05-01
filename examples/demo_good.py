"""
demo_good.py — Same chatbot with all waste patterns fixed.

Fixes applied vs demo_bad.py:
1. System prompt marked cacheable (cache_control)
2. History capped at last 4 turns
3. Only tools relevant to current intent loaded
4. Error bodies stripped to one line before injecting into context

Run with: python examples/demo_good.py
No API key needed — uses analyse() directly to simulate calls.
"""

from token_lens import analyse

# Same system prompt — but now marked cacheable
SYSTEM_PROMPT = [
    {
        "type": "text",
        "text": """You are a clinical decision support assistant for doctors.
You have deep knowledge of fertility, ENT, and cosmetic surgery specialties.
Always follow safety protocols: never silently assign a document to a patient.
Confirm every assignment. If there is a mismatch between document content and
patient name on record, stop and ask. Maintain the speed of the doctor's thinking.
Never go silent during processing. Send proactive updates for any step over 5s.
You must be concise, precise, and evidence-based. Cite guidelines where relevant.
Do not hallucinate drug doses or diagnostic criteria. When uncertain, say so.
""" + ("Additional clinical context. " * 30),
        "cache_control": {"type": "ephemeral"},  # FIX 1: cacheable
    }
]

# FIX 3: Only load tools relevant to lab/patient data queries
LAB_TOOLS = [
    {"name": "get_patient_summary", "description": "Get full patient summary",      "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}}},
    {"name": "get_lab_results",     "description": "Get lab results for a patient", "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}, "test": {"type": "string"}}}},
    {"name": "search_guidelines",   "description": "Search clinical guidelines",    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}},
]

HISTORY_WINDOW = 4  # FIX 2: rolling window

TURNS = [
    ("user", "Show me Priya Sharma's latest lab results."),
    ("assistant", "Here are Priya Sharma's latest results: FSH 8.2 mIU/mL (Day 3), AMH 1.4 ng/mL, LH 5.1 mIU/mL. All within acceptable ranges for her age."),
    ("user", "What was her AMH last cycle?"),
    ("assistant", "Previous cycle AMH was 1.6 ng/mL. There's a slight downward trend worth monitoring."),
    ("user", "Error: 500 Internal Server Error\nTraceback (most recent call last):\n  File 'processor.py', line 142, in get_guidelines\nKeyError: 'specialty'\nFailed to retrieve ESHRE guidelines."),
    ("assistant", "Guidelines service unavailable. Proceeding without."),  # FIX 4: stripped error in response
    ("user", "Ok skip that. What does her AMH trend suggest?"),            # FIX 4: error body NOT re-injected
    ("assistant", "A decline from 1.6 to 1.4 ng/mL over one cycle may indicate early diminished ovarian reserve. Recommend repeat testing in 3 months."),
    ("user", "What's the recommended next step per ESHRE?"),
]

def cap_history(history: list, window: int) -> list:
    """Keep only the last N messages."""
    return history[-window:] if len(history) > window else history


print("\n" + "="*60)
print("  DEMO: Good version — all waste patterns fixed")
print("="*60)

history = []
for i, (role, content) in enumerate(TURNS):
    if role == "assistant":
        history.append({"role": "assistant", "content": content})
        continue

    history.append({"role": "user", "content": content})

    request = {
        "model": "claude-sonnet-4-6",
        "system": SYSTEM_PROMPT,                 # FIX 1: cache_control set
        "messages": cap_history(history[:-1], HISTORY_WINDOW),  # FIX 2: capped
        "tools": LAB_TOOLS,                      # FIX 3: 3 tools, not 10
        "max_tokens": 512,                       # FIX 5: bounded output
    }

    user_turn = sum(1 for m in history if m["role"] == "user")
    print(f"\n{'─'*60}")
    print(f"  Turn {user_turn}: \"{content[:55]}{'...' if len(content)>55 else ''}\"")
    print(f"{'─'*60}")

    analyse(request, output_tokens=180)
