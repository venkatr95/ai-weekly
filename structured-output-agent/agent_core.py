"""Structured Output Agent — schema, LLM calls, validation, and retry logic."""

import json
import os
import re
import time
from enum import Enum

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

# ── Default models per provider ────────────────────────────────────────────────

PROVIDER_DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash",
    "anthropic": "claude-sonnet-4-5",
    "openai": "gpt-4o",
    "grok": "grok-3",
}

MAX_RETRIES = 3


# ── Schema (source of truth) ───────────────────────────────────────────────────

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
    """Validated domain object for a customer support ticket."""

    category: Category
    priority: Priority
    sentiment: Sentiment

    issue: str = Field(min_length=1, description="Short slug, e.g. 'payment_failed'")

    amount: float | None = Field(default=None, description="Monetary amount if mentioned")
    currency: str | None = Field(default=None, description="ISO 4217 currency code if mentioned")

    refund_requested: bool

    summary: str = Field(
        min_length=10,
        max_length=500,
        description="One-sentence summary of the customer's issue",
    )


# ── Prompts ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a customer-support information extraction system.

Extract structured information from the customer's message and return it as a
JSON object that exactly matches the schema below.

Schema:
{schema}

Rules:
1. Only extract information explicitly stated in the message.
2. Never invent an amount or currency — use null if not mentioned.
3. Set refund_requested true only if the customer explicitly asks for a refund.
4. Choose category and priority strictly from the allowed enum values.
5. Return ONLY the JSON object — no markdown, no code fences, no explanation.
6. The summary must be a single complete sentence (10–500 characters).
7. The issue field must be a short underscore slug (e.g. "payment_failed").

Priority guidance:
- critical: service down, data loss, security breach
- high: financial impact, repeated failures, significant disruption
- medium: intermittent issues, general problems
- low: questions, minor inconveniences, feature requests"""


def _build_initial_prompt(message: str) -> str:
    schema = json.dumps(SupportTicket.model_json_schema(), indent=2)
    system = SYSTEM_PROMPT.format(schema=schema)
    return system + f"\n\nCustomer message:\n{message}"


def _build_retry_prompt(message: str, error: str, attempt: int) -> str:
    schema = json.dumps(SupportTicket.model_json_schema(), indent=2)
    system = SYSTEM_PROMPT.format(schema=schema)
    return (
        system
        + f"\n\nYour previous response (attempt {attempt}) failed validation:\n{error}"
        + f"\n\nFix the error(s) above and return the corrected JSON.\n\nCustomer message:\n{message}"
    )


# ── LLM calls ─────────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers the model sometimes adds."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _call_llm(prompt: str) -> str:
    """Call the configured LLM provider and return the raw response text."""
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider not in PROVIDER_DEFAULT_MODELS:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            f"Supported: {', '.join(PROVIDER_DEFAULT_MODELS)}"
        )
    model = os.getenv("LLM_MODEL") or PROVIDER_DEFAULT_MODELS[provider]

    if provider == "gemini":
        import google.generativeai as genai
        from google.generativeai.types import GenerationConfig

        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        client = genai.GenerativeModel(
            model_name=model,
            generation_config=GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        response = client.generate_content(prompt)
        return response.text

    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    if provider == "grok":
        from openai import OpenAI  # xAI uses OpenAI-compatible API

        client = OpenAI(
            api_key=os.getenv("XAI_API_KEY"),
            base_url="https://api.x.ai/v1",
        )
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content


# ── Core extraction with retry ─────────────────────────────────────────────────

def _format_validation_error(exc: ValidationError) -> str:
    """Turn a Pydantic ValidationError into a human-readable correction string."""
    lines = []
    for err in exc.errors():
        loc = " → ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "unknown error")
        got = err.get("input", "<missing>")
        lines.append(f"  Field '{loc}': {msg} (got: {got!r})")
    return "Validation errors:\n" + "\n".join(lines)


def extract_ticket(message: str, verbose: bool = True) -> SupportTicket:
    """
    Extract a validated SupportTicket from a natural-language message.

    Retries up to MAX_RETRIES times, feeding the Pydantic validation error
    back into the prompt each time so the model can self-correct.

    Args:
        message: Raw customer support message.
        verbose: Print attempt progress to stdout.

    Returns:
        A validated SupportTicket object.

    Raises:
        RuntimeError: If all retry attempts fail.
    """
    start = time.monotonic()
    last_error: str | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        if verbose:
            if attempt == 1:
                print(f"  Extracting... (attempt {attempt}/{MAX_RETRIES})")
            else:
                print(f"  Retrying... (attempt {attempt}/{MAX_RETRIES})")

        # Build prompt — include error feedback on retries
        if last_error:
            prompt = _build_retry_prompt(message, last_error, attempt - 1)
        else:
            prompt = _build_initial_prompt(message)

        try:
            raw = _call_llm(prompt)
            cleaned = _strip_fences(raw)
            parsed = json.loads(cleaned)
            ticket = SupportTicket.model_validate(parsed)

            elapsed = (time.monotonic() - start) * 1000
            if verbose:
                print(f"  ✓ Valid — {attempt} attempt(s), {elapsed:.0f}ms")
            return ticket

        except json.JSONDecodeError as exc:
            last_error = f"JSON parse error: {exc}\nYour response was:\n{raw[:300]}"
            if verbose:
                print(f"  ✗ JSON parse error on attempt {attempt}")

        except ValidationError as exc:
            last_error = _format_validation_error(exc)
            if verbose:
                print(f"  ✗ Validation error on attempt {attempt}:")
                for line in last_error.splitlines():
                    print(f"    {line}")

        except Exception as exc:  # noqa: BLE001
            # LLM API error — not worth retrying
            raise RuntimeError(f"LLM error: {exc}") from exc

    raise RuntimeError(
        f"Failed to produce valid structured output after {MAX_RETRIES} attempt(s).\n"
        f"Last error:\n{last_error}"
    )
