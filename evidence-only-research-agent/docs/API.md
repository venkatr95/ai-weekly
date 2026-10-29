# API

The CLI is the supported interface. The Python modules are importable for tests and embedding in another script.

```python
from evidence_agent.config import Settings
from evidence_agent.pipeline import ResearchPipeline

settings = Settings(index_dir="data/index", generation_provider="extractive")
pipeline = ResearchPipeline(settings)
pipeline.index_path("documents", rebuild=False)
response, passages = pipeline.ask("What limitations were reported?")
print(response.model_dump())
```

`response` is an `AnswerResponse`. `passages` are the chunks retrieved for the full question. Their scores are ranking signals only.

## JSON object

`python cli.py ask "..." --format json` prints this object. `provider` and `passages_retrieved` are included in addition to the fields required by the PRD.

| Field | Type | Meaning |
|---|---|---|
| `question` | string | The question that was asked. |
| `answer` | string | A short structural summary. Findings live in `claims`, not in extra prose. |
| `claims` | array | Findings that passed verification. |
| `citations` | array | Excerpts those findings rely on. |
| `unanswered_questions` | array | Subquestions that were not answered. |
| `conflicts` | array | Disagreements. `resolved` is false. |
| `abstained` | boolean | True when no verified claim and no verified conflict remain. |
| `limitations` | array of strings | Limits of this answer. |
| `provider` | string | `extractive`, `xai`, or `openai_compatible`. |
| `passages_retrieved` | integer | How many passages the full question retrieved. |

Each claim:

| Field | Meaning |
|---|---|
| `id` | `claim-1`, `claim-2`, ... |
| `text` | The finding. For the extractive provider this is a source sentence. |
| `evidence_status` | `supported`, `interpretation`, or `unsupported`. Extractive output uses `supported`. |
| `citation_ids` | Ids in `citations`. |
| `verification_status` | Returned claims are `verified`. Rejected claims are omitted. |

Each citation:

| Field | Meaning |
|---|---|
| `id` | `cit-1`, ... |
| `chunk_id` | Id accepted by `show-source`. |
| `source_path` | Path relative to the indexed folder, with forward slashes. |
| `page` | 1-based PDF page, or null for text and Markdown. |
| `excerpt` | Whitespace-normalized verbatim span of the chunk. |
| `valid` | True. Invalid citations are not returned. |
| `supports_claim` | True. A verbatim quote that does not overlap the claim is rejected. |
| `rejection_reason` | Null on returned citations. |

Each unanswered question has `question`, `reason`, `detail`, and `citation_ids`. `reason` is one of `missing_documents`, `insufficient_retrieval`, `conflicting_evidence`, `ambiguous_wording`, `insufficient_evidence`.

Each conflict has `topic`, `positions`, `resolved`, and `note`. A position has `summary` and `citation_ids`.

The machine-readable schema is `AnswerResponse.model_json_schema()` in `src/evidence_agent/schemas.py`.

## Example

A conflicting question returns both sides. This is the shape from a local extractive run. Chunk ids and page numbers are omitted here; the live command prints them.

```json
{
  "question": "Did Intervention X produce a statistically significant improvement in sleep onset latency?",
  "answer": "The retrieved sources disagree. Each position is cited separately, and the conflict is unresolved. The documents support 2 cited statements.",
  "abstained": false,
  "claims": [
    {
      "id": "claim-1",
      "text": "Intervention X did not produce a statistically significant improvement in sleep onset latency.",
      "evidence_status": "supported",
      "citation_ids": ["cit-1"],
      "verification_status": "verified"
    },
    {
      "id": "claim-2",
      "text": "Intervention X produced a statistically significant improvement in sleep onset latency.",
      "evidence_status": "supported",
      "citation_ids": ["cit-2"],
      "verification_status": "verified"
    }
  ],
  "conflicts": [
    {
      "topic": "improvement, intervention, latency, onset, produce, significant",
      "resolved": false,
      "note": "The documents do not resolve this conflict."
    }
  ]
}
```

The full object also includes the citations, pages, and limitations. Generate it with:

```bash
py -3 cli.py ask "Did Intervention X produce a statistically significant improvement in sleep onset latency?" --format json
```

## Errors

Library calls raise `evidence_agent.errors.EvidenceAgentError` subclasses: `ConfigurationError`, `IndexNotFoundError`, `CorruptIndexError`, `EmptyCorpusError`, `ProviderError`, and `GenerationError`. The CLI prints the message and exits 2. Error text is scrubbed so it does not include API keys.
