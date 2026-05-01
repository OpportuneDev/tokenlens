# token-lens — Architecture & How It Works

## What it does

token-lens intercepts LLM API calls, breaks down every request into labelled token segments, scores it against known waste patterns, and reports what's being wasted and why — per call, in real time.

---

## File Structure

```
token_lens/
├── __init__.py        Public API — patch(), unpatch(), analyse()
├── patch.py           SDK-level interception
├── core.py            Analysis pipeline — entry point for all analysis
├── analyzer.py        Request decomposition into segments
├── tokenizer.py       Token counting (tiktoken)
├── patterns.py        Waste pattern detection
├── reporter.py        Terminal output (Rich)
├── store.py           Session persistence (JSON)
├── dashboard.py       Streamlit visual dashboard
└── cli.py             CLI entry point
```

---

## How a call flows through the system

```
Your app makes an LLM call
        ↓
patch.py intercepts it (SDK-level monkey patch)
        ↓
The real API call is made — response returned to your app unchanged
        ↓
core.py → analyse()
        ↓
analyzer.py — decompose request into segments
        ↓
patterns.py — check each segment against waste patterns
        ↓
reporter.py — print to terminal
store.py    — write to ~/.tokenlens/session.json
        ↓
dashboard.py reads session.json, auto-refreshes every 3s
```

Nothing in your app changes. The response your app receives is identical to what the API returns.

---

## Layer 1: Interception (patch.py)

`token_lens.patch()` monkey-patches the SDK method directly:

```python
# For Anthropic
target = anthropic.resources.messages.Messages
original_create = target.create

def patched_create(self, **kwargs):
    response = original_create(self, **kwargs)  # real call first
    analyse(kwargs, output_tokens=...)           # then analyse
    return response                              # app gets real response

target.create = patched_create
```

Because this patches the SDK class itself (not a client instance), it intercepts every call made by any framework — LangChain, LlamaIndex, CrewAI, direct SDK calls — as long as they ultimately use the Anthropic or OpenAI Python SDK.

**What it can't intercept:**
- Node.js / Go / other language SDKs (Python only)
- HTTP calls made directly without the SDK
- Frameworks that bundle their own HTTP client and bypass the SDK

---

## Layer 2: Request Decomposition (analyzer.py)

Every LLM request is a dict. `decompose()` parses it and labels each part:

```
Request
├── system          → TokenSegment("system_prompt", N tokens, {cached: bool})
├── messages[:-1]   → TokenSegment("conversation_history", N tokens, {turns: N})
├── messages[-1]    → TokenSegment("user_message", N tokens)
└── tools           → TokenSegment("tool_definitions", N tokens, {count: N})
```

The last message is always the current user turn. Everything before it is history.

For Anthropic requests, `system` can be a string or a list of content blocks (the latter is how `cache_control` is applied). The analyzer handles both.

For OpenAI requests, the system prompt is the first message with `role=system`.

---

## Layer 3: Token Counting (tokenizer.py)

Uses `tiktoken` with `cl100k_base` encoding — OpenAI's tokenizer, used as an approximation for both OpenAI and Anthropic models.

**Accuracy:** ~95% for typical English content. Can drift on heavy code, non-English text, or structured formats (JSON, XML). Accurate enough for waste detection — you're catching patterns like "40% of your context is tool definitions", not billing users to the cent.

**Fallback:** if `tiktoken` isn't installed, counts `len(text) // 4` (4 chars ≈ 1 token). Much less accurate but functional.

---

## Layer 4: Waste Pattern Detection (patterns.py)

Each pattern is a checker function. All checkers run on every call. Each returns a `WasteFlag` or `None`.

### Current patterns

**UNCACHED_SYSTEM_PROMPT**
Triggers when system prompt > 200 tokens and no `cache_control` is present.
Anthropic's prompt caching reduces repeated system prompt cost by ~90%.
Fix: add `{"type": "ephemeral"}` cache_control to the system prompt block.

**UNBOUNDED_HISTORY**
Triggers when conversation history > 10 turns.
Each turn resends the full prior history. A 20-turn conversation costs ~10x what turn 1 costs.
Fix: rolling window of 8 turns, or summarise older turns.

**ERROR_ACCUMULATION**
Scans history messages for error-pattern text (HTTP codes, tracebacks, "failed", "exception").
Error bodies injected into context are expensive and carry no useful signal beyond the status code.
Fix: strip error responses to `{status, type, retryable}` before injecting.

**LARGE_TOOL_DEFINITIONS**
Triggers when tool definitions > 800 tokens.
Tools are serialised into every request whether used or not.
Fix: classify intent first, load only tools relevant to that intent.

**VERBOSE_OUTPUT**
Triggers when output/input token ratio > 0.6.
Output tokens cost 3–5x more than input. Verbose outputs compound fast.
Fix: explicit `max_tokens`, concise response format instructions.

**LARGE_SINGLE_CONTEXT_BLOCK**
Triggers when any single non-system message > 2000 tokens.
Usually indicates unfiltered RAG chunks or raw API response injection.
Fix: similarity threshold on RAG retrieval, strip irrelevant fields from API responses.

### Adding a new pattern

```python
# patterns.py
def check_my_pattern(segments, request, output_tokens=None):
    s = _seg(segments, "conversation_history")
    if not s:
        return None
    # your logic
    return WasteFlag(
        pattern="MY_PATTERN",
        severity=WasteSeverity.HIGH,
        tokens_wasted=123,
        detail="What happened.",
        fix="How to fix it.",
    )

# Register it
_CHECKERS.append(check_my_pattern)
```

---

## Layer 5: Scoring

```
efficiency_score = 100 - (recoverable_tokens / total_input_tokens × 100)
```

- **100** — no waste detected
- **80+** — healthy
- **50–80** — worth investigating
- **<50** — significant waste

`recoverable_tokens` is the sum of `tokens_wasted` across all flags. It's capped at `total_input_tokens` to avoid scores below 0.

The score is a heuristic, not a precise measurement. Waste estimates within each pattern are conservative approximations (e.g. UNBOUNDED_HISTORY estimates that the last 8 turns cover 80% of relevant context — this is a reasonable assumption for most chat applications, not a guarantee).

---

## Layer 6: Cost Calculation (reporter.py)

Input and output tokens are priced separately because output tokens cost 3–5x more.

```python
_PRICING = {
    "claude-sonnet": (3.0, 15.0),   # (input $/MTok, output $/MTok)
    "claude-haiku":  (0.25, 1.25),
    "gpt-4o":        (2.5, 10.0),
    ...
}
```

`VERBOSE_OUTPUT` flags use output pricing. All other flags use input pricing (they represent tokens sent, not generated).

**Important:** prices are hardcoded and will go stale. Update `_PRICING` in `reporter.py` when providers change their rates.

---

## Layer 7: Persistence (store.py)

Every analysis is appended to `~/.tokenlens/session.json` as a JSON record.

```json
{
  "ts": 1746123456.78,
  "request_id": "a1b2c3d4",
  "model": "claude-sonnet-4-6",
  "efficiency_score": 58,
  "recoverable_tokens": 466,
  "segments": [...],
  "flags": [...]
}
```

This file is the data source for the dashboard. It persists across terminal sessions. Use `token-lens dashboard` → "Clear session" button to reset it.

---

## Layer 8: Dashboard (dashboard.py)

Streamlit app that reads `~/.tokenlens/session.json` and auto-refreshes every 3 seconds using `streamlit-autorefresh`.

**Four panels:**
1. **Top metrics** — call count, average efficiency score, total tokens wasted, waste %
2. **Efficiency per call** — line chart with Good (80) and Warn (50) thresholds
3. **Token composition** — donut chart of last call's segments (how context is distributed)
4. **Token usage per call** — stacked bar of input + output tokens per call
5. **Waste flags table** — all flags across the session, colour-coded by severity

**Run it:**
```bash
token-lens dashboard
# or
streamlit run token_lens/dashboard.py
```

---

## Data flow summary

```
patch() → real API call → analyse() → reporter (terminal) + store (JSON) → dashboard
```

The terminal output and dashboard show the same data. The dashboard aggregates across the session; the terminal shows each call as it happens.

---

## Known limitations

1. **Python only** — patch() works on Python SDKs. Node.js (saarthi-clinical) needs a separate integration.
2. **Approximate token counts** — tiktoken is ~95% accurate for Anthropic, not exact.
3. **Hardcoded pricing** — will drift as providers change rates.
4. **RAG detection is heuristic** — LARGE_SINGLE_CONTEXT_BLOCK catches obvious cases; distributed RAG chunks spread across history won't be caught.
5. **No model routing detection** — can't tell if you're using Opus for a task that Haiku could handle.
6. **Single process** — patch() only intercepts calls made by the same Python process. Multiple workers each need their own patch() call.
