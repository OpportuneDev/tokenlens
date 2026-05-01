# The Hidden Tax: Token Waste Is Quietly Draining Your AI Budget

Most developers optimising AI costs start in the wrong place.

They compare model pricing tables. They negotiate enterprise tiers. They benchmark GPT-4o vs Claude vs Gemini on cost per million tokens.

None of that matters as much as what you're actually putting in the context window.

Token costs have two levers: price per token (the model you choose) and tokens consumed (what you send and receive). The industry obsesses over the first. The second is where the real money is.

This is a deep dive into the second lever — the patterns that silently inflate token usage, the math behind why it compounds, and a diagnostic tool that tells you exactly where your tokens are going.

---

## The Asymmetry You Need to Understand First

Output tokens cost 3–5x more than input tokens across every major provider.

| Provider | Input (per MTok) | Output (per MTok) | Multiplier |
|---|---|---|---|
| Claude Sonnet 4.6 | $3.00 | $15.00 | 5x |
| GPT-4o | $2.50 | $10.00 | 4x |
| Gemini 1.5 Pro | $1.25 | $5.00 | 4x |

This asymmetry reshapes how you should think about every design decision. Asking for a JSON object when you need one field, letting the model "think out loud" in production, not setting `max_tokens` — these are all output token decisions with real cost consequences.

Keep this multiplier in mind throughout everything that follows.

---

## Part 1: Status Codes and Where Errors Actually Cost You

When an LLM-powered system makes a tool call or external API request, it gets back a status code. How that code (and its payload) lands in your context window determines whether you're spending tokens wisely or burning them.

### API Layer vs LLM Layer

Not all 5xx errors are equal. Where in the stack the failure originates determines both billing impact and what the right response is.

**API layer** is everything before your prompt reaches the model: load balancers, routing, authentication, rate limiting, infrastructure overload. If the request never reached the model, you aren't charged.

**LLM layer** is what happens after your prompt is accepted and inference begins: tokenisation, context processing, actual generation, safety checks.

| Scenario | Tokens consumed | Charged |
|---|---|---|
| 5xx at API layer (never reached model) | No | No |
| 5xx at LLM layer, pre-inference | No | No |
| 5xx mid-generation (streaming) | Input yes, partial output | Often yes |
| Stream drops after N chunks | Input + partial output | Yes |

The dangerous case is streaming. If you open a stream, receive some tokens, and then the connection drops — your input was already processed. Retrying means paying for those input tokens twice, and you may have a partial response sitting in your context that's worse than nothing.

### The Opacity Problem

Providers mostly don't tell you which layer the error originated from.

Anthropic's error types (`api_error`, `overloaded_error`, `rate_limit_error`) give some signal. Their non-standard `529` specifically means infrastructure overload — pre-inference, safe to retry. A generic `500` with a structured JSON body probably reached the model. An HTML 500 page almost certainly didn't.

OpenAI is less granular. `server_error` tells you almost nothing about where it failed.

The most reliable signal you have is whether you received any stream chunks before the failure:

```python
chunks_received = 0
try:
    for chunk in stream:
        chunks_received += 1
except Exception as e:
    if chunks_received == 0:
        retry()           # Pre-inference — nothing was spent
    else:
        handle_partial()  # Input tokens were consumed — don't retry blindly
```

### The Retry Multiplier

A single unhandled error in an agentic loop doesn't just cost what the error costs. It multiplies:

```
Turn 1:  Tool call → 500 response        (800 tokens in context)
Turn 2:  Model retries → another 500     (800 more tokens)
Turn 3:  Model explains what happened    (300 tokens)
Turn 4:  Third retry, different params   (800 tokens)
```

~3,000 tokens wasted before the loop gives up — before the model's own output tokens on each turn.

At a 5% error rate across 100K daily calls with 3 retries per failure: **~7.5 million wasted tokens per day from errors alone.**

```python
def normalise_error(response):
    return {
        "status": response.status_code,
        "error": response.json().get("error", {}).get("type", "unknown"),
        "retryable": response.status_code in (429, 500, 502, 503)
    }
```

Status code plus one field. The model doesn't need the stack trace.

---

## Part 2: The Eight Waste Patterns

### 1. Uncached System Prompts

Your system prompt runs on every API call. 2,000-token system prompt × 1M calls/month = 2 billion tokens of pure repetition.

```
Without caching: 2,000 tokens × $3/MTok × 1M calls = $6,000/month
With caching:    2,000 tokens × $0.30/MTok × 1M calls = $600/month
```

One config change. 10x cost difference.

Fix: keep system prompt static, move dynamic content into the first user message, add `cache_control`.

### 2. Unbounded Conversation History

Each turn re-sends the entire history:

```
Turn 1:    500 tokens sent
Turn 10:  7,000 tokens sent
Turn 20: 18,000 tokens sent
```

A 20-turn conversation costs ~10x what a naive per-turn calculation suggests. Cap at 8–10 turns and summarise older context.

### 3. RAG Over-retrieval

`k=10` at 500 tokens/chunk = 5,000 tokens before the model reads the question. If 6 chunks are irrelevant, 3,000 tokens wasted.

```python
# Before
chunks = retriever.get(query, k=10)

# After
chunks = [c for c in retriever.get(query, k=10) if c.score > 0.70][:4]
```

### 4. Tool Definition Overhead

150–400 tokens per tool definition, every call, whether used or not. 15 tools = up to 6,000 tokens of constant overhead.

Fix: classify intent first, inject only tools relevant to that intent.

### 5. Error Body Injection

An HTML 500 page: 500–3,000 tokens of markup. A stack trace: potentially thousands. The model needs to know something failed and whether it's retryable. Nothing else.

### 6. Wrong Model for the Task

| Task | Right model | Wrong model | Cost delta |
|---|---|---|---|
| Intent classification | Haiku | Opus | ~60x |
| Field extraction | Haiku | GPT-4o | ~17x |
| Clinical reasoning | Sonnet | — | baseline |

Route simple queries to cheap models. The accuracy delta rarely justifies the cost delta.

### 7. No Semantic Caching

The same question asked 50,000 times a month should cost tokens once. Semantic caching on production workloads achieves 20–40% cache hit rates. Most teams have none.

### 8. Dev and Test on Production Models

10 developers × 500 test calls/day on the most expensive model = 5,000 daily wasted calls. Enforce model tiers by environment.

---

## Part 3: Diagnosing Your Own System

I built **token-lens** to make waste visible. It decomposes every API request into labelled segments, scores it against waste patterns, and gives a dollar-value estimate for what's recoverable.

```
Token Breakdown

  Segment                Tokens   % of context
  ─────────────────────────────────────────────
  system_prompt             336          30.1%   ← UNCACHED
  conversation_history      302          27.0%   ← 12 turns
  user_message               15           1.3%
  tool_definitions          465          41.6%   ← 10 tools, 2 ever used
  TOTAL                    1118

Efficiency score: 58/100   Recoverable: 466 tokens (41.7%)

  HIGH    UNCACHED_SYSTEM_PROMPT    336t    $50/mo at 50K calls
  MEDIUM  UNBOUNDED_HISTORY         130t    $19/mo
  MEDIUM  LARGE_TOOL_DEFINITIONS    465t    $69/mo

Total recoverable: $139/month at 50,000 calls/month
```

Drop-in wrapper, zero other changes required:

```python
from token_lens import DiagnosticWrapper
import anthropic

client = DiagnosticWrapper(anthropic.Anthropic(), monthly_calls=50_000)

# All existing calls unchanged — report prints automatically
response = client.messages.create(model="claude-sonnet-4-6", messages=[...])
```

Works with OpenAI too. Or analyse a request dict without any live API call:

```python
from token_lens import analyse
analyse(request_dict, output_tokens=500, monthly_calls=50_000)
```

---

## Fix Priority

| Fix | Savings potential | Effort |
|---|---|---|
| Prompt caching | 80–90% on system prompt | Low — config |
| Cap conversation history | 40–70% on chat | Low — truncation |
| RAG similarity threshold | 30–60% | Low — one filter |
| Model routing | 50–90% on routed queries | Medium — classifier |
| Semantic caching | 20–40% | Medium — infra |
| Dynamic tool loading | 10–30% | Medium |
| Normalise error bodies | 5–20% | Low — wrapper |

---

## The One Thing

Before any of the above: **instrument token usage per feature.**

You can't fix what you can't measure. Log input tokens, output tokens, model, and endpoint per call. That data tells you exactly where to focus. Everything else follows from it.

---

*token-lens is open source — link in comments.*
