# Sanskrit TTS

Generate Sanskrit speech with [Indic Parler-TTS](https://huggingface.co/ai4bharat/indic-parler-tts) (`ai4bharat/indic-parler-tts`).

## Requirements

- Python 3.10+ (tested with 3.12)
- Optional: NVIDIA GPU + CUDA for faster generation (CPU works, but is slower)
- First run downloads the model from Hugging Face (needs network access)

## Install dependencies

From the project root:

```powershell
python -m venv tts
.\tts\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On macOS/Linux:

```bash
python -m venv tts
source tts/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks venv activation on Windows, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate again.

## Run the notebook

With the venv activated:

```powershell
jupyter notebook sanskrit_tts.ipynb
```

Or open `sanskrit_tts.ipynb` in VS Code / Cursor and select the `tts` kernel.

### Notebook flow

1. Run the first code cell to load the model and tokenizers (one-time per session).
2. Run the cell that defines `generate_sanskrit_audio(...)`.
3. Run an example cell (or call the function with your own Sanskrit text) to write an `.mp3` file.

## Run the script instead

```powershell
python sanskrit_tts.py
```

This writes `sanskrit_output.mp3` in the project root. The script uses the same generator and default voice as the page.

## Run the web UI

From the project directory, with the venv activated:

```powershell
streamlit run streamlit_app.py
```

The page opens on the Gaṇeśa śloka. Paste other Devanāgarī, or load the Śānti mantra. The sidebar holds the English voice description. A blank description uses the measured, reverent default. Upload a `.txt` file when you want that file read instead of the text box.

Generate plays the recitation in the browser and offers a WAV download. The first generation downloads Indic Parler-TTS. CUDA is used when it is available. The text is spoken as written. Audio stays on this machine.

```powershell
pytest -q
```

Page tests use a stand-in engine, so they do not download the model.

Refer `PRD.md` for the detailed analysis
