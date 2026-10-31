# Architecture

The design reference is [../ARCHITECTURE.md](../ARCHITECTURE.md). This page is the short operational view.

## Data flow

```text
answer + sources
    -> document loader / text extractor
    -> sentence segmenter
    -> claim extractor
    -> evidence retriever
    -> claim verifier
    -> evidence validator
    -> Pydantic AuditReport
    -> Markdown or JSON
```

Retrieval only chooses passages. The verifier assigns the status. The validator then checks that every quote is a real span of the extracted text.

## Status rules that the report enforces

- Supported means a passage states the claim.
- Partially supported is reported separately and is not added to the supported count.
- Contradicted requires a conflicting passage.
- Unsupported means the documents do not contain enough evidence. The explanation says that missing evidence is not a contradiction.
- Unverifiable is used for opinions, recommendations, and non-factual lines.
- Evidence coverage is supported claims divided by factual claims.

`AuditReport` rejects a summary whose counts or coverage do not match the claims.

## Provider boundary

The heuristic provider is the default and does not use the network. The xAI provider may propose text, but the validator and the numeric checker still run. See [SECURITY.md](SECURITY.md) for how source text is sent.
