"""
Example: analyse a simulated Anthropic request without making a real API call.
Run with: python examples/anthropic_example.py
"""
import sys
sys.path.insert(0, "..")

from token_lens import analyse

# Simulate a request that has several common waste patterns:
#   - large uncached system prompt
#   - long conversation history
#   - many tool definitions
request = {
    "model": "claude-sonnet-4-6",
    "system": (
        "You are a clinical decision support assistant for Dr. Ramanan. "
        "You have deep knowledge of fertility, ENT, and cosmetic surgery specialties. "
        "Always follow SAFETY-1: never silently assign a document to a patient. "
        "Confirm every assignment. If there is a mismatch between document content and "
        "patient name on record, stop and ask. Maintain the speed of the doctor's thinking. "
        "Never go silent during processing. Send proactive updates for any step over 5 seconds. "
        "You must be concise, precise, and evidence-based. Cite guidelines where relevant. "
        "Do not hallucinate drug doses or diagnostic criteria. "
        "When uncertain, say so clearly and suggest consulting the appropriate specialist. "
        # padding to simulate a real 1000+ token system prompt
        "Additional context: " + ("This is placeholder context. " * 40)
    ),
    "messages": [
        {"role": "user",      "content": "Show me Priya Sharma's last visit summary."},
        {"role": "assistant", "content": "Here is the summary for Priya Sharma from 2026-02-10..."},
        {"role": "user",      "content": "What were her FSH levels?"},
        {"role": "assistant", "content": "Her FSH was 8.2 mIU/mL on day 3. Within normal range."},
        {"role": "user",      "content": "Compare with her previous cycle."},
        {"role": "assistant", "content": "Previous cycle: FSH 7.9 mIU/mL. Stable trend."},
        {"role": "user",      "content": "Any concerns with her AMH?"},
        {"role": "assistant", "content": "AMH was 1.4 ng/mL. Slightly below average for age 32."},
        {"role": "user",      "content": "What does the literature say about this range?"},
        {"role": "assistant", "content": "AMH 1.0–3.5 ng/mL is considered normal for 32. Her value suggests slightly diminished ovarian reserve. ESHRE guidelines recommend..."},
        {"role": "user",      "content": "Error: 500 Internal Server Error\nTraceback (most recent call last):\n  File 'processor.py', line 142\nKeyError: 'patient_id'\nRequest failed. Please retry."},
        {"role": "assistant", "content": "I encountered an error retrieving that data. Let me try again."},
        {"role": "user",      "content": "Error: 500 Internal Server Error\nTraceback (most recent call last):\n  File 'processor.py', line 142\nKeyError: 'patient_id'\nRequest failed. Please retry."},
        {"role": "assistant", "content": "Still encountering errors. The system may be temporarily unavailable."},
        {"role": "user",      "content": "OK skip that. What's her recommended next step?"},
    ],
    "tools": [
        {"name": "get_patient_summary",  "description": "Get patient summary", "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}}},
        {"name": "get_lab_results",      "description": "Get lab results for a patient", "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}, "test_name": {"type": "string"}}}},
        {"name": "search_documents",     "description": "Search patient documents", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}},
        {"name": "get_visit_notes",      "description": "Retrieve visit notes", "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}, "limit": {"type": "integer"}}}},
        {"name": "get_medications",      "description": "Get current medications", "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}}},
        {"name": "get_imaging_reports",  "description": "Retrieve imaging reports", "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}}}},
        {"name": "search_guidelines",    "description": "Search clinical guidelines", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "specialty": {"type": "string"}}}},
        {"name": "create_referral",      "description": "Create a referral", "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}, "to_specialty": {"type": "string"}}}},
        {"name": "schedule_followup",    "description": "Schedule a follow-up", "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}, "days": {"type": "integer"}}}},
        {"name": "send_patient_report",  "description": "Send report to patient", "input_schema": {"type": "object", "properties": {"patient_id": {"type": "string"}, "report_type": {"type": "string"}}}},
    ],
    "max_tokens": 1024,
}

# Simulate 500 output tokens
# No monthly_calls needed — the wrapper tracks observed rate automatically
analyse(request, output_tokens=500)
