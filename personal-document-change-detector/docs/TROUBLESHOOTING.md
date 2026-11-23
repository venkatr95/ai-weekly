# Troubleshooting

The CLI prints `Error: …` and exits with status 2 for an input, parse, configuration, or provider failure. A completed comparison exits 0 even when many high-importance changes are reported.

## Encrypted PDF

`ParseError`: the PDF is encrypted. Remove the password and run again. The detector does not ask for the password.

## Empty file or scan / OCR

`InputError`: no text could be extracted. Common causes:

- The file is empty.
- A PDF has no text layer (image-only scan). The warning names pages that look like scans. This project does not OCR them. Use a PDF with a text layer, or convert to `.txt` / `.md` after OCR elsewhere.

## Unsupported document type

You named a file whose suffix is not `.pdf`, `.docx`, `.txt`, `.md`, or `.markdown`. Convert it, or pass a supported path.

## Document not found

`--old` or `--new` points to a missing path, or a directory was given where a file is required.

## The file is not valid UTF-8

Text and Markdown sources must be UTF-8. Re-save the file as UTF-8.

## XAI_API_KEY is missing

`--provider xai` and `DETECTOR_PROVIDER=xai` need `XAI_API_KEY` in the environment or in `.env`. The heuristic provider does not need a key. Use it when you want a reproducible local report.

## The model provider returned an error

`ProviderError` includes the HTTP status or says the provider could not be reached. It does not include the API key. Check `XAI_BASE_URL`, the model id, and network access. A response that is not the expected JSON is also a provider error. Run again with `--provider heuristic` if you want the offline report.

## A quotation was dropped or not validated

The warning or `evidence_validated` flag says the quotation does not appear in the extracted text. That can happen when a model paraphrases. Diffs still list the local previous/updated spans. The heuristic provider quotes those spans directly.

## Expected changes are missing

- Try without `--min-importance high` so medium and lower items remain.
- Confirm headings align; heavily rewritten section titles can reduce pairing quality.
- Formatting-only differences are hidden unless `--include-formatting` is set.
- Unchanged clauses (for example annual leave at 25 days) correctly produce no change row.

## `PyMuPDF is required`

Run `pip install -r requirements.txt` inside the project virtualenv. PDF support needs PyMuPDF (`fitz`).

## `streamlit` is not recognized

Install the project requirements, then start the page from `personal-document-change-detector`:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The page uses the same virtualenv as `cli.py`. A bad PDF, an unsupported type, or a missing `XAI_API_KEY` is shown on the page. Those are the same errors the CLI prints.

## pytest cannot import the package

Run pytest from the project directory. `pytest.ini` puts `src` on the Python path. Use the project virtualenv so Pydantic, PyMuPDF, and python-docx are installed.

## Euro characters look wrong in the Windows console

The CLI sets standard output to UTF-8. If the console font still cannot show `€`, open the JSON report or redirect to a file:

```bash
python cli.py compare --old examples/documents/employment_v1.md --new examples/documents/employment_v2.md --format json --output report.json
```
