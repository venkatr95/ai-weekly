# Evaluation

```bash
python cli.py evaluate
```

This ingests `examples/meetings` into a temporary index, asks every question in `examples/questions.json`, and prints a pass or fail line. `--output report.json` writes the `EvaluationReport`. `--meetings` and `--questions` select other files. `--index-dir` keeps the temporary corpus. Without it, evaluate does not touch `data/index`.

`examples/history_questions.json` scores the earlier March transcripts in `examples/history`. Those files are a regression set. The planning transcript is the canonical example in the PRD.

The automated checks cover citation validity, abstention, explicit versus inferred wording, deadline changes, and unresolved questions. They do not report a word-error rate. Transcription accuracy needs a reference transcript and a speech provider, and this repository does not invent that score. Speaker-mapping tests check that a diarizer name is discarded and that a manual map is kept. Deadline tests check that a month and day without a meeting date stays unresolved.

A question passes when:

- `abstain` matches `Answer.abstained`
- every `answer_contains` string is in the answer text, ignoring case
- no `answer_excludes` string is in the answer text
- every `evidence_contains` string is in some evidence quote
- `speaker`, `meeting`, and `timestamp` match at least one evidence passage when they are set

The bundled file has nine questions: the seven product questions, an abstention about a mobile app that was never discussed, and an inferred runbook task that must not be called an explicit commitment. The exit code is 0 only when all of them pass.

The score does not measure a language model. It checks that the rule extractor and the router keep owners, deadlines, revisions, and abstentions tied to the sample transcripts.
