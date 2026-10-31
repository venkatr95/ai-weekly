# Troubleshooting

The CLI prints `Error: …` and exits with status 2 for an input, parse, configuration, or provider failure. A completed audit exits 0 even when some claims are contradicted. `evaluate` exits 1 when a labeled case fails.

## The answer file is empty

`InputError`: the answer file is empty, or a JSON request has an empty `answer`. Put the generated answer in the file.

## No source text could be extracted

Every file was empty, or a scanned PDF had no text layer. Use a PDF with a text layer, or pass `.txt` or `.md`. The warning names pages that look like scans. This project does not OCR them.

## Unsupported source type

You named a file whose suffix is not `.txt`, `.md`, `.markdown`, `.pdf`, or `.json`. Convert it, or put it in a directory if you want it skipped with a warning instead of a hard error.

## Could not read a PDF

- Encrypted: remove the password and run again. The auditor does not ask for the password.
- Unreadable or corrupt: the message includes the exception type. The file is not given a guessed transcription.
- `PyMuPDF is required`: run `pip install -r requirements.txt` inside the project virtualenv.

## The file is not valid UTF-8

Text and Markdown sources must be UTF-8. Re-save the file as UTF-8.

## audit requires --answer and --sources

Pass both, or pass `--input` with a JSON request. `--input` and `--answer` together are rejected.

## XAI_API_KEY is missing

`--provider xai` and `AUDITOR_PROVIDER=xai` need `XAI_API_KEY` in the environment or in `.env`. The heuristic provider does not need a key. Use it when you want a reproducible local report.

## The model provider returned an error

`ProviderError` includes the HTTP status or says the provider could not be reached. It does not include the API key. Check `XAI_BASE_URL`, the model id, and network access. A response that is not the expected JSON is also a provider error. The command does not quietly fall back to the heuristic result. Run again with `--provider heuristic` if you want the offline report.

## A quotation was dropped

The note says the quotation does not appear in the source. That happens when a model paraphrases. The status is then based on quotations that do match, or it becomes unsupported when none remain. The heuristic provider quotes source sentences directly, so this note is for the model path.

## Coverage looks low

Coverage is supported claims divided by factual claims. Partially supported and contradicted claims do not count as supported. In the bundled demo the 25% claim is contradicted because the figures show 20%, so coverage is 25.0, not 50.

## pytest cannot import the package

Run pytest from the project directory. `pytest.ini` puts `src` on the Python path. Use the project virtualenv so Pydantic and PyMuPDF are installed.

## Euro characters look wrong in the Windows console

The CLI sets standard output to UTF-8. If the console font still cannot show `€`, open the JSON report or redirect to a file:

```bash
python cli.py audit --answer examples/answer.txt --sources examples/sources --format json --output report.json
```
