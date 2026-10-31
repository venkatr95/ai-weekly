# Usage

## Audit files

```bash
python cli.py audit --answer answer.txt --sources source1.pdf source2.pdf source3.pdf
python cli.py audit --answer answer.txt --sources ./sources/ --question "What happened in 2025?"
python cli.py audit --answer answer.txt --sources ./sources/ --format json --output report.json
```

`--format` is `markdown` or `json`. Markdown is the default. `--output` also writes the report to a file. The process still prints it.

`--sources` takes one or more files or directories. Files in a directory are ordered by path. Source ids are `S1`, `S2`, `S3`, and so on, unless a JSON source sets `source_id`.

A plain-text or Markdown source may start with a title line. The title is metadata and is not treated as evidence.

```text
Title: Annual report

Revenue for 2025 amounted to €120 million.
```

A Markdown file can use a level-1 heading instead:

```markdown
# Hiring note

The company hired 100 employees.
```

A JSON source file is one document:

```json
{"title": "Financial statement", "text": "Net profit for the financial year was €15 million."}
```

## JSON request

`examples/audit_input.json` is a complete request:

```bash
python cli.py audit --input examples/audit_input.json --format json
```

The object has `answer`, optional `question`, and `sources`. Each source has `text` or `path`, plus optional `source_id` and `title`. `--question` overrides the question in the file. Do not pass `--answer` together with `--input`.

## Claims only

```bash
python cli.py extract-claims --answer examples/answer.txt
```

This prints the claims and does not verify them.

## Benchmark

```bash
python cli.py evaluate
```

This runs `examples/benchmark.json` through the heuristic provider and prints accuracy. The labeled statuses are the judge. See [EVALUATION.md](EVALUATION.md).

## Python

```python
from answer_auditor import audit, extract_claims

claims = extract_claims(open("answer.txt", encoding="utf-8").read())
report = audit(
    open("answer.txt", encoding="utf-8").read(),
    ["examples/sources"],
    question="What happened in 2025?",
)
```

`report.model_dump(mode="json")` is the JSON document. Field definitions are in [API.md](API.md).

## How to read a status

- Supported: use the quotation. It states the claim.
- Partially supported: the quotation establishes only part of the claim, or the percentage was calculated and is not written in the source.
- Contradicted: the quotation conflicts with the claim. Do not treat the claim as supported.
- Unsupported: the supplied documents do not show this. That absence does not prove the claim is false.
- Unverifiable: the line is an opinion, a recommendation, or not a factual claim.

Evidence coverage is supported claims divided by factual claims. A partially supported claim does not increase coverage.
