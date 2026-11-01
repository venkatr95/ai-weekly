# Installation

Python 3.11 or newer is required. The package dependencies are Pydantic and pytest.

```bash
cd email-to-action-agent
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest -q
```

On macOS and Linux, activate the virtualenv with `source .venv/bin/activate`.

No API key is required. The extractor does not call a model.
