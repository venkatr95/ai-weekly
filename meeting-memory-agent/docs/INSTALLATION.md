# Installation

Python 3.11 or newer.

```bash
cd meeting-memory-agent
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS or Linux, activate with `source .venv/bin/activate`.

Optional local transcription:

```bash
pip install faster-whisper
```

Set `MEETING_TRANSCRIBER=whisper` only after that install. The default `sidecar` mode does not need it.

Copy `.env.example` to `.env` if you want a custom index directory or size limit. The sample meetings run with no `.env`.

Check the install:

```bash
python cli.py ingest examples/meetings
python cli.py evaluate
py -3 -m pytest
```

Run `pytest` from this directory. From the collection root it collects other projects.
