# Evaluation

The benchmark is `examples/benchmark.json`. Each case has an answer, sources, and the statuses a person assigned. `python cli.py evaluate` runs the heuristic auditor and compares the result with those labels.

The labels are the judge. The auditor is not asked to grade its own output, and an LLM is not used as the scorer.

## What is measured

| Check | What it tells you |
| --- | --- |
| Verification accuracy | The share of cases whose statuses match the labels, in order. |
| Citation validity | The share of quotations that occur in the labeled source text. |
| Claim substrings | Whether the extracted claim text still contains the labeled wording. |

A case passes only when the statuses, the claim wording, and the quotations all match. Verification accuracy ignores citation failures so the two numbers can be read separately. On the bundled file both should be 100%.

## Labeled situations

The file includes a directly supported figure, an explicit percentage, a percentage that has to be calculated, a wrong percentage, a contradicted profit figure, an implied workforce change, a claim with no relevant source, an opinion, two sources that disagree, a compound sentence, and a negated sentence.

## The sample 25% claim

The product example says revenue increased by 25% and shows €120 million against €100 million. Those figures are a 20% increase: `(120 - 100) / 100 = 0.20`. The illustrative table in the requirements marks 25% as supported. That table is sample layout, not the arithmetic. This auditor marks the 25% claim contradicted and quotes the revenue sentence. A claim that says 20% is partially supported, because the sources imply 20% and do not state the percentage. A source that itself says "increased by 20%" is supported.

Partial support is never added to the supported count. In the three-source demo, one of four factual claims is supported, so evidence coverage is 25.0.

## Tests

`pytest -q` covers loading, segmentation, claim splitting, retrieval, verification, quotation checks, report math, the CLI, instruction text inside a source, and a fake model response. The model test checks that a confident "supported" status and an invented quotation do not survive a numeric contradiction.

## What this does not measure

The benchmark does not measure latency or API cost, because the default provider makes no network call. It also does not measure free-form qualitative reading beyond the wording overlap described in the architecture. Add a labeled case to `examples/benchmark.json` when you need a new situation to stay fixed.
