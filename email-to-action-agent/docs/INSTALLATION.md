# Installation

Python 3.11 or newer is required. The package dependencies are Pydantic, pytest, and Streamlit.

```bash
cd email-to-action-agent
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest -q
streamlit run streamlit_app.py
```

On macOS and Linux, activate the virtualenv with `source .venv/bin/activate`.

No API key is required. The extractor does not call a model. Optional Gmail and Outlook tokens are documented in `.env.example` and are not read by `analyze()`.
