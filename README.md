# token-lens

Diagnose token waste in your LLM API calls.

Tells you which tokens are being wasted and why — per call, no configuration needed.

## Install

```bash
pip install git+https://github.com/OpportuneDev/tokenlens.git
```

## Usage

### Drop-in wrapper

```python
from token_lens import DiagnosticWrapper
import anthropic

client = DiagnosticWrapper(anthropic.Anthropic())

response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "..."}],
)
# Waste report prints automatically after every call
```

Works with OpenAI too:

```python
from token_lens import DiagnosticWrapper
import openai

client = DiagnosticWrapper(openai.OpenAI())
response = client.chat.completions.create(model="gpt-4o", messages=[...])
```

### Analyse a request dict directly

```python
from token_lens import analyse

analyse(request_dict, output_tokens=500)
```

### CLI

```bash
token-lens request.json
cat request.json | token-lens -
```

## What it detects

| Pattern | What it means |
|---|---|
| `UNCACHED_SYSTEM_PROMPT` | System prompt repeated on every call, not cached |
| `UNBOUNDED_HISTORY` | Conversation history growing without truncation |
| `ERROR_ACCUMULATION` | Error content re-sent in context across retries |
| `LARGE_TOOL_DEFINITIONS` | Tool definitions consuming significant context |
| `VERBOSE_OUTPUT` | Output/input ratio suggests unnecessarily long responses |
| `LARGE_SINGLE_CONTEXT_BLOCK` | Single message block unusually large (likely RAG dump) |

## Sample output

```
╭──────────────────────────────────────────────────────╮
│ token-lens  ·  claude-sonnet-4-6  ·  anthropic        │
╰──────────────────────────────────────────────────────╯

Token Breakdown

  Segment                Tokens   % of context
  ─────────────────────────────────────────────
  system_prompt             336          30.1%
  conversation_history      302          27.0%
  user_message               15           1.3%
  tool_definitions          465          41.6%
  output (generated)        500

  TOTAL                    1118           100%

Efficiency score: 58/100   Recoverable tokens: 466 (41.7%)

Waste Flags

  Severity  Pattern                  Tokens wasted  Cost wasted
  ─────────────────────────────────────────────────────────────
  HIGH      UNCACHED_SYSTEM_PROMPT             336   $0.001008
  MEDIUM    UNBOUNDED_HISTORY                  130   $0.000390

  Cost wasted this call: $0.001398  (input @ $3.00/MTok, output @ $15.00/MTok)
```

## Notes

- **Token counts** use `tiktoken` (`cl100k_base`) as a local approximation. Accurate to ~95% for Anthropic models on typical English content.
- **Cost calculation** is model-specific (input and output priced separately). Unknown models fall back to Sonnet pricing. Prices are hardcoded — update `_PRICING` in `reporter.py` if they change.
- **Silent mode**: `DiagnosticWrapper(client, silent=True)` — runs analysis without printing, returns `RequestAnalysis` object.

## Requirements

- Python 3.10+
- `tiktoken`
- `rich` (optional, for formatted output)
