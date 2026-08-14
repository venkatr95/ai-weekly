# PRD: Structured Output Agent

**Owner:** Venkat Madhavan
**Status:** v1 implemented
**Last updated:** 2026-08-14

## 1. Problem Statement

LLMs naturally produce inconsistent responses — different field names, missing fields, invalid types, extra information, malformed JSON, and hallucinated values. Without a validation layer you can't trust the output enough to wire it into a real application.

## 2. Goal

Build a local agent that takes an unstructured natural-language input and guarantees the output conforms to a typed schema. The important part isn't generating JSON — the important part is that the application can **trust** the output.

The MVP use case is **customer support ticket extraction**: turn a free-text support message into a validated `SupportTicket` object.

Input:

> "My payment failed twice yesterday and I was charged €49.99. Please refund me. This is urgent."

Output:

```json
{
  "category": "billing",
  "priority": "high",
  "sentiment": "negative",
  "issue": "payment_failed",
  "amount": 49.99,
  "currency": "EUR",
  "refund_requested": true,
  "summary": "Customer reports two failed payment attempts and requests a refund."
}
```

## 3. Non-Goals (v1)

- No REST API / FastAPI server — just a local Python script.
- No database or persistence — one extraction per run.
- No multi-schema support — `SupportTicket` only for now.
- No web UI.

## 4. Target User

A technical user (AI engineer, developer) who wants to see structured extraction working locally and understand how validation + retry works — before layering on an orchestration framework.

## 5. User Stories

1. As a user, I want to paste a support message and get back a clean JSON object I can trust, so I can wire it into a downstream system.
2. As a user, I want the agent to retry automatically when the LLM returns invalid output, not silently fail.
3. As a user, I want to see what the model extracted and how many attempts it took.

## 6. Functional Requirements

| # | Requirement | Priority |
|---|---|---|
| 1 | Accept a free-text message (CLI arg or `--interactive` mode) | P0 |
| 2 | Extract structured data via LLM and return it as a `SupportTicket` object | P0 |
| 3 | Validate output with Pydantic — never return invalid data | P0 |
| 4 | Retry up to 3 times on validation failure, feeding the error back into the prompt | P0 |
| 5 | Print the result as formatted JSON to stdout | P0 |
| 6 | Show attempt count and latency | P1 |
| 7 | Interactive mode: loop asking for messages until user quits | P1 |

## 7. Schema (Source of Truth)

```python
class Category(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    SHIPPING = "shipping"
    OTHER = "other"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"

class SupportTicket(BaseModel):
    category: Category
    priority: Priority
    sentiment: Sentiment
    issue: str                  # short slug e.g. "payment_failed"
    amount: float | None        # monetary amount if mentioned
    currency: str | None        # ISO 4217 code if mentioned
    refund_requested: bool
    summary: str                # 10–500 char one-sentence summary
```

## 8. Technical Approach

- **Language**: Python 3.10+, local virtualenv.
- **LLM**: Multi-provider via `LLM_PROVIDER` env var (default: `gemini`). Supported: Google Gemini, Anthropic Claude, OpenAI, Grok.
- **Structured output**: `response_mime_type: application/json` (Gemini) or `response_format: json_object` (OpenAI/compatible). Falls back to JSON parsing from response text.
- **Validation**: Pydantic v2 — every response is model-validated before it's returned.
- **Retry**: On `ValidationError`, the error string is appended to the next prompt so the model can self-correct. Max 3 attempts.
- **Config**: API keys via `.env`, auto-loaded via `python-dotenv`.

## 9. Retry Strategy

The agent feeds the validation error back into the correction prompt:

```
Attempt 1: extract from "My payment failed..."
← LLM returns: {"category": "billing_issue", ...}   # invalid enum
✗ Pydantic: category must be one of: billing, technical, account...

Attempt 2: "Your previous response failed validation.
            Field 'category' must be one of: billing, technical...
            Fix and return valid JSON."
← LLM returns: {"category": "billing", ...}          # valid ✓
```

## 10. File Layout

```
structured-output-agent/
├── agent_core.py      # schema, extraction logic, retry loop
├── extract.py         # CLI entry point
├── requirements.txt
├── .env.example
├── PRD.md
└── README.md
```

## 11. Implementation Status

| Item | Status |
|---|---|
| Pydantic schema (`SupportTicket`) | ✅ Done — `agent_core.py` |
| LLM extraction with retry | ✅ Done — `agent_core.py` |
| Multi-provider LLM support | ✅ Done — `LLM_PROVIDER` env var |
| Validation feedback in retry prompt | ✅ Done |
| CLI with `--interactive` mode | ✅ Done — `extract.py` |
| FastAPI server | ❌ Not built — deliberately out of scope for v1 |

## 12. Future Work (post-v1)

1. **REST API** — wrap `extract_ticket()` in FastAPI for programmatic use.
2. **Multiple schemas** — generalise `agent_core.py` to accept any Pydantic model.
3. **Batch mode** — read messages from a CSV/JSONL file, emit results to a file.
4. **Confidence score** — ask the model to rate its own confidence alongside the extraction.
