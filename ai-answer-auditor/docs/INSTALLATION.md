# Installation

Requires Python 3.11 or newer.

On Windows, `python` may not be on `PATH`. Use the `py` launcher:

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS and Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Dependencies are pinned in `requirements.txt`:

- Pydantic, for the report schema
- PyMuPDF, for PDF text extraction
- pytest, for the tests

Check the install:

```bash
pytest -q
python cli.py audit --answer examples/answer.txt --sources examples/sources
```

No API key is required for the default heuristic provider. See [CONFIGURATION.md](CONFIGURATION.md) if you want the optional xAI provider.

PDF extraction needs a text layer. Scanned pages are reported as needing OCR and are not read as text. This project does not install an OCR engine.
