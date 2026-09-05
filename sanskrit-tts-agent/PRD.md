# Sanskrit TTS — Product Requirements Document

## Overview

Local Sanskrit text-to-speech toolkit using [Indic Parler-TTS](https://huggingface.co/ai4bharat/indic-parler-tts) (`ai4bharat/indic-parler-tts`). Generate clear, reverent Devanāgarī recitation audio for ślokas and mantras via a Jupyter notebook or a Python script.

## Goal

Given Sanskrit text in Devanāgarī and an optional natural-language voice description, produce a playable `.mp3` file with precise pronunciation and chanting-appropriate pace.

## Deliverables

| Artifact | Role |
|----------|------|
| `sanskrit_tts.ipynb` | Interactive load → generate → play workflow |
| `sanskrit_tts.py` | One-shot script that writes `sanskrit_output.mp3` |
| `requirements.txt` | Python dependencies |
| `README.md` | Install and run instructions |
| Sample audio | `ganesha_sloka.mp3`, `shanti_mantra.mp3`, `sanskrit_output.mp3` |

## Requirements

### Runtime

- Python 3.10+ (tested with 3.12)
- Isolated venv
- Optional NVIDIA GPU + CUDA (CPU supported, slower)
- First run downloads model weights from Hugging Face (network required once)

### Dependencies

- `torch`, `torchaudio`
- `transformers==4.46.1`
- `soundfile`
- `accelerate`
- `ipykernel`, `jupyter`
- `git+https://github.com/huggingface/parler-tts.git`

### Device selection

- Use `cuda:0` when CUDA is available
- Otherwise use `cpu`
- Report the device at model load time

### Inputs

1. **Text (required)** — Sanskrit in Devanāgarī; preserve Unicode, daṇḍa (`।` / `॥`), and verse line breaks; do not translate or rewrite the text
2. **Voice description (optional)** — English natural-language style prompt for Parler-TTS; if omitted, use a chanting-oriented default

### Default voice description

The default description must specify:

- Traditional Sanskrit male reciter
- Deep, clear, warm, reverent voice
- Precise syllable articulation
- Steady, measured, solemn, devotional pace
- Gentle pauses at pāda boundaries; longer pauses between verses
- Meditative, non-theatrical delivery
- Clean studio audio with no background music, reverb, or sound effects

### Outputs

- Audio file at the model sampling rate (default container: `.mp3`)
- Console confirmation: `Saved: <filename>`
- In the notebook: inline playback via `IPython.display.Audio`

### API

Notebook helper:

```python
generate_sanskrit_audio(text, output_filename="sanskrit_output.mp3", description=None)
```

Script entrypoint:

```powershell
python sanskrit_tts.py
```

Writes `sanskrit_output.mp3` in the project root.

## Notebook flow

1. Load model and tokenizers once per session
2. Define `generate_sanskrit_audio(...)`
3. Run example cells (or call the function with custom text) to write `.mp3` files

## Example texts

**Gaṇeśa śloka** → `ganesha_sloka.mp3`

```
प्रणम्य शिरसा देवं गौरीपुत्रं विनायकम् ।
भक्तावासं स्मरेन्नित्यमायुःकामार्थसिद्धये ॥
```

**Śānti mantra** → `shanti_mantra.mp3`

```
ॐ सह नाववतु ।
सह नौ भुनक्तु ।
सह वीर्यं करवावहै ॥
```

## Quality bar

| Criterion | Expectation |
|-----------|-------------|
| Intelligibility | Syllables are clear and followable |
| Pace | Slow–moderate; suitable for chanting |
| Prosody | Verse-like pauses at pāda / verse boundaries |
| Tone | Reverent and meditative |
| Noise | No music, hiss beds, or invented effects |
| Consistency | Stable voice, volume, and tempo within a multi-line verse |

## Non-goals

- Fine-tuning or training new TTS models
- Real-time streaming TTS server
- Mixing, EQ, reverb, or other DAW features
- Shipping model weights inside this folder (download on demand)
- Automatic transliteration between scripts

## Acceptance checklist

- [ ] Fresh venv installs from `requirements.txt`
- [ ] Notebook loads the model and defines `generate_sanskrit_audio`
- [ ] Gaṇeśa example writes `ganesha_sloka.mp3` and plays in the notebook
- [ ] Śānti example writes `shanti_mantra.mp3` and plays in the notebook
- [ ] `python sanskrit_tts.py` writes `sanskrit_output.mp3`
- [ ] Generation completes on CPU
- [ ] CUDA is used when available
- [ ] README matches actual install and run steps
