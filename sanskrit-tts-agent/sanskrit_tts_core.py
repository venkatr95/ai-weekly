"""Local Sanskrit speech with Indic Parler-TTS.

The model stays unloaded until generate() or load() runs. Callers can pass
an engine into generate_sanskrit_audio() so tests do not download weights.
"""

from __future__ import annotations

import io
import struct
import wave
from pathlib import Path

MODEL_ID = "ai4bharat/indic-parler-tts"
MAX_TEXT_CHARS = 2000

DEFAULT_DESCRIPTION = """
Aryan is a trained Sanskrit male reciter performing a traditional Vedic hymn.
He has a deep, clear, warm and reverent male voice with precise Sanskrit pronunciation.
He articulates every Sanskrit syllable distinctly and naturally, without swallowing or merging consonants.
The recitation is steady, measured, solemn and devotional.
He follows the natural rhythm and meter of the Sanskrit hymn, maintaining consistent timing and breath control.
Each pāda is clearly articulated with a gentle, natural pause at its boundary, and there is a slightly longer pause between complete verses.
The voice is focused and meditative, with restrained expression and no theatrical acting.
The recitation sounds like a disciplined traditional Sanskrit pāṭha rather than ordinary spoken language.
Maintain consistent pronunciation, volume, pitch and tempo throughout.
Use clean studio-quality audio with a dry, natural acoustic environment and no background music, instruments, echo, reverb, or sound effects.
""".strip()

GANESHA_SLOKA = """
प्रणम्य शिरसा देवं गौरीपुत्रं विनायकम् ।
भक्तावासं स्मरेन्नित्यमायुःकामार्थसिद्धये ॥
""".strip()

SHANTI_MANTRA = """
ॐ सह नाववतु ।
सह नौ भुनक्तु ।
सह वीर्यं करवावहै ॥
""".strip()

EXAMPLES = {
    "Ganesha sloka": GANESHA_SLOKA,
    "Shanti mantra": SHANTI_MANTRA,
}


class TTSError(Exception):
    """A problem the page or the script can show without a traceback."""


class AudioClip:
    """Mono waveform at the model's sample rate."""

    def __init__(self, samples, sample_rate: int) -> None:
        self.samples = samples
        self.sample_rate = int(sample_rate)

    def wav_bytes(self) -> bytes:
        return encode_wav(self.samples, self.sample_rate)


class SanskritEngine:
    """One loaded Indic Parler-TTS model for this process."""

    def __init__(self) -> None:
        self.model = None
        self.tokenizer = None
        self.description_tokenizer = None
        self.device: str | None = None
        self.sample_rate: int | None = None

    def load(self) -> SanskritEngine:
        if self.model is not None:
            return self
        import torch
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        print(f"Loading model on {self.device}...")
        self.model = ParlerTTSForConditionalGeneration.from_pretrained(MODEL_ID).to(self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        encoder_name = self.model.config.text_encoder._name_or_path
        self.description_tokenizer = AutoTokenizer.from_pretrained(encoder_name)
        self.sample_rate = int(self.model.config.sampling_rate)
        print("Model loaded successfully!")
        return self

    def generate(self, text: str, description: str | None = None) -> AudioClip:
        text = normalize_text(text)
        description = normalize_description(description)
        self.load()
        assert self.tokenizer is not None
        assert self.description_tokenizer is not None
        assert self.model is not None

        description_inputs = self.description_tokenizer(description, return_tensors="pt").to(self.device)
        text_inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        generation = self.model.generate(
            input_ids=description_inputs.input_ids,
            attention_mask=description_inputs.attention_mask,
            prompt_input_ids=text_inputs.input_ids,
            prompt_attention_mask=text_inputs.attention_mask,
        )
        audio = generation.cpu().numpy().squeeze()
        return AudioClip(audio, int(self.model.config.sampling_rate))


_ENGINE: SanskritEngine | None = None


def normalize_text(text: str | None) -> str:
    """Strip the ends. Keep Devanāgarī, daṇḍa, and verse breaks as written."""

    if text is None or not str(text).strip():
        raise TTSError("Sanskrit text is empty.")
    cleaned = str(text).strip()
    if len(cleaned) > MAX_TEXT_CHARS:
        raise TTSError(f"Sanskrit text is longer than {MAX_TEXT_CHARS} characters.")
    return cleaned


def normalize_description(description: str | None) -> str:
    """Use the chanting voice when the description is blank."""

    if description is None or not str(description).strip():
        return DEFAULT_DESCRIPTION
    cleaned = str(description).strip()
    if len(cleaned) > MAX_TEXT_CHARS:
        raise TTSError(f"Voice description is longer than {MAX_TEXT_CHARS} characters.")
    return cleaned


def encode_wav(samples, sample_rate: int) -> bytes:
    """PCM WAV bytes. Values outside -1 to 1 are clipped."""

    rate = int(sample_rate)
    if rate <= 0:
        raise TTSError("Sample rate must be a positive integer.")
    frames = bytearray()
    count = 0
    for value in _mono(samples):
        clipped = float(value)
        if clipped > 1.0:
            clipped = 1.0
        elif clipped < -1.0:
            clipped = -1.0
        frames += struct.pack("<h", int(round(clipped * 32767)))
        count += 1
    if count == 0:
        raise TTSError("The model returned no audio.")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames)
    return buffer.getvalue()


def _mono(samples):
    shape = getattr(samples, "shape", None)
    if shape is not None and len(shape) == 2:
        if shape[0] <= 8 and shape[0] < shape[1]:
            return samples[0]
        return samples[:, 0]
    return samples


def get_engine() -> SanskritEngine:
    """The process-wide engine. The weights load on the first generate()."""

    global _ENGINE
    if _ENGINE is None:
        _ENGINE = SanskritEngine()
    return _ENGINE


def set_engine(engine: SanskritEngine | None) -> None:
    """Replace the process-wide engine. Tests pass a stand-in. None clears it."""

    global _ENGINE
    _ENGINE = engine


def write_clip(path: Path, clip: AudioClip) -> None:
    """Write WAV with the stdlib, and any other suffix with soundfile."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".wav":
        path.write_bytes(clip.wav_bytes())
        return
    import soundfile as sf

    sf.write(str(path), clip.samples, clip.sample_rate)


def generate_sanskrit_audio(
    text: str,
    output_filename: str = "sanskrit_output.mp3",
    description: str | None = None,
    engine: SanskritEngine | None = None,
) -> Path:
    """Generate one clip and write it. Prints the notebook's Saved line."""

    if engine is None:
        engine = get_engine()
    clip = engine.generate(text, description)
    path = Path(output_filename)
    write_clip(path, clip)
    print(f"Saved: {output_filename}")
    return path
