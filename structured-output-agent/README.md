# Structured Output Agent

A local agent that takes a natural-language customer support message and returns a **validated, typed** `SupportTicket` object. The key guarantee: the application can trust the output.

See [PRD.md](PRD.md) for the full product spec.

## How it works

```
message → LLM (JSON mode) → Pydantic validate → SupportTicket
                                    ↓ fail
                             retry prompt + error → LLM → validate (up to 3×)
```

Each retry feeds the exact Pydantic validation error back to the model so it self-corrects — not a blind retry.

## Quick start

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your API key
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY (or whichever provider you choose)

# 4. Run
python extract.py "My payment failed twice yesterday and I was charged 49.99. Please refund me."
```

## Usage

```bash
# Single message as argument
python extract.py "My subscription was cancelled without warning."

# Interactive mode — keeps asking for messages
python extract.py --interactive

# Pipe from stdin
echo "I can't log in to my account." | python extract.py
```

## Example output

```
Message: My payment failed twice yesterday and I was charged €49.99. Please refund me. This is urgent.

  Extracting... (attempt 1/3)
  ✓ Valid — 1 attempt(s), 834ms

Result:
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

## Schema

```python
class SupportTicket(BaseModel):
    category: Category          # billing | technical | account | shipping | other
    priority: Priority          # low | medium | high | critical
    sentiment: Sentiment        # positive | neutral | negative
    issue: str                  # short slug e.g. "payment_failed"
    amount: float | None        # monetary amount if mentioned, else null
    currency: str | None        # ISO 4217 code if mentioned, else null
    refund_requested: bool      # True only if customer explicitly asks
    summary: str                # 10–500 char one-sentence summary
```

## Providers

Change `LLM_PROVIDER` in `.env`:

| Provider | Default model | Key env var |
|---|---|---|
| `gemini` (default) | `gemini-2.0-flash` | `GOOGLE_API_KEY` |
| `anthropic` | `claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| `openai` | `gpt-4o` | `OPENAI_API_KEY` |
| `grok` | `grok-3` | `XAI_API_KEY` |

Override the model with `LLM_MODEL=gemini-2.5-pro` (or any model name for the chosen provider).

## Files

```
structured-output-agent/
├── agent_core.py   # schema, LLM calls, retry logic
├── extract.py      # CLI entry point
├── requirements.txt
├── .env.example
├── PRD.md
└── README.md
```
