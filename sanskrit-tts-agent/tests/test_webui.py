"""The web UI uses the same generator as the script.

Page tests install a stand-in engine so they do not download model weights.
"""

from __future__ import annotations

import importlib
import io
import struct
import wave
from pathlib import Path

import pytest

from sanskrit_tts_core import (
    DEFAULT_DESCRIPTION,
    GANESHA_SLOKA,
    SHANTI_MANTRA,
    TTSError,
    AudioClip,
    SanskritEngine,
    generate_sanskrit_audio,
    normalize_description,
    normalize_text,
    set_engine,
)
from streamlit_app import output_name, public_error, read_upload, synthesize

ROOT = Path(__file__).resolve().parents[1]


class FakeEngine:
    def __init__(self, fail: str | None = None) -> None:
        self.fail = fail
        self.calls: list[tuple[str, str]] = []
        self.loads = 0

    def load(self):
        self.loads += 1
        if self.fail:
            raise RuntimeError(self.fail)
        return self

    def generate(self, text, description=None):
        text = normalize_text(text)
        description = normalize_description(description)
        self.load()
        self.calls.append((text, description))
        if self.fail:
            raise RuntimeError(self.fail)
        return AudioClip((0.0, 0.5, -0.5, 0.25), 16000)


@pytest.fixture(autouse=True)
def _clear_engine():
    set_engine(None)
    yield
    set_engine(None)


def test_default_voice_matches_the_chanting_brief():
    voice = DEFAULT_DESCRIPTION.lower()
    for phrase in (
        "sanskrit male",
        "deep, clear, warm",
        "reverent",
        "syllable",
        "measured",
        "solemn",
        "devotional",
        "pause",
        "meditative",
        "no background music",
        "reverb",
    ):
        assert phrase in voice


def test_normalize_text_keeps_devanagari_and_rejects_empty():
    verse = "प्रणम्य शिरसा देवं ।\n\nभक्तावासं ॥"
    assert normalize_text(f"  {verse}\n") == verse
    with pytest.raises(TTSError, match="empty"):
        normalize_text(" \n")
    with pytest.raises(TTSError, match="2000"):
        normalize_text("अ" * 2001)


def test_blank_description_uses_the_default():
    assert normalize_description(None) == DEFAULT_DESCRIPTION
    assert normalize_description("  \n") == DEFAULT_DESCRIPTION
    assert normalize_description("  A clear voice.  ") == "A clear voice."
    with pytest.raises(TTSError, match="Voice description"):
        normalize_description("a" * 2001)


def test_wav_bytes_round_trip():
    data = AudioClip((0.0, 0.5, -1.0, 1.2), 8000).wav_bytes()
    assert data.startswith(b"RIFF")
    with wave.open(io.BytesIO(data), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == 8000
        frames = struct.unpack("<4h", handle.readframes(4))
    assert frames[0] == 0
    assert frames[1] == 16384
    assert frames[2] == -32767
    assert frames[3] == 32767
    with pytest.raises(TTSError, match="no audio"):
        AudioClip((), 16000).wav_bytes()
    with pytest.raises(TTSError, match="Sample rate"):
        AudioClip((0.1,), 0).wav_bytes()


def test_generate_writes_wav_without_loading_weights(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    engine = FakeEngine()
    target = tmp_path / "nested" / "out.wav"
    path = generate_sanskrit_audio(f"  {SHANTI_MANTRA}  ", str(target), description="  ", engine=engine)
    assert path == target
    assert target.read_bytes().startswith(b"RIFF")
    assert engine.calls == [(SHANTI_MANTRA, DEFAULT_DESCRIPTION)]
    assert engine.loads == 1
    assert f"Saved: {target}" in capsys.readouterr().out


def test_script_import_does_not_load_the_model(monkeypatch: pytest.MonkeyPatch):
    def fail_load(self):
        raise AssertionError("model loaded")

    monkeypatch.setattr(SanskritEngine, "load", fail_load)
    import sanskrit_tts

    importlib.reload(sanskrit_tts)
    assert sanskrit_tts.GANESHA_SLOKA == GANESHA_SLOKA


def test_read_upload_and_output_name():
    assert read_upload(r"..\sloka.txt", "ॐ ।\n".encode("utf-8")) == "ॐ ।"
    assert read_upload("sloka.txt", "\ufeffॐ ।\n".encode("utf-8")) == "ॐ ।"
    assert output_name(GANESHA_SLOKA) == "ganesha_sloka.wav"
    assert output_name(SHANTI_MANTRA) == "shanti_mantra.wav"
    assert output_name("ॐ नमः शिवाय ।") == "sanskrit_output.wav"
    with pytest.raises(TTSError, match="empty"):
        read_upload("sloka.txt", b" \n")
    with pytest.raises(TTSError, match="UTF-8"):
        read_upload("sloka.txt", b"\xff")
    with pytest.raises(TTSError, match=".txt"):
        read_upload("sloka.md", b"\xe0\xa4\x93\n")
    with pytest.raises(TTSError, match="64 KB"):
        read_upload("sloka.txt", b"a" * (64 * 1024 + 1))
    long_error = public_error(RuntimeError("x" * 600))
    assert long_error.endswith("...")
    assert len(long_error) == 503


def test_synthesize_uses_a_supplied_engine_and_the_default_voice():
    engine = FakeEngine()
    clip = synthesize(f"  {GANESHA_SLOKA}\n", "   ", engine=engine)
    assert engine.calls == [(GANESHA_SLOKA, DEFAULT_DESCRIPTION)]
    assert clip.wav_bytes().startswith(b"RIFF")
    with pytest.raises(TTSError, match="empty"):
        synthesize(" ", DEFAULT_DESCRIPTION, engine=engine)
    assert engine.loads == 1


def test_page_opens_on_the_ganesha_sloka_without_loading_a_model(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    def fail_load(self):
        raise AssertionError("model loaded")

    monkeypatch.setattr(SanskritEngine, "load", fail_load)
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    assert not app.exception
    assert app.text_area(key="text").value == GANESHA_SLOKA
    assert "reverent" in app.text_area(key="description").value
    assert app.session_state.wav is None


def test_page_generates_plays_and_names_the_download():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    engine = FakeEngine()
    set_engine(engine)
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    app.button(key="generate").click().run()
    assert not app.exception
    assert engine.calls == [(GANESHA_SLOKA, DEFAULT_DESCRIPTION)]
    assert app.session_state.wav.startswith(b"RIFF")
    assert app.session_state.download_name == "ganesha_sloka.wav"
    assert app.success[0].value == "Recitation ready."
    assert app.download_button[0].label == "Download WAV"
    assert list(app.get("audio"))


def test_page_empty_text_does_not_call_the_engine():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    engine = FakeEngine()
    set_engine(engine)
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    app.text_area(key="text").set_value("  \n").run()
    app.button(key="generate").click().run()
    assert engine.calls == []
    assert engine.loads == 0
    assert any("empty" in item.value for item in app.error)
    assert app.session_state.wav is None
    assert not app.exception


def test_page_load_example_replaces_the_text_and_clears_audio():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    engine = FakeEngine()
    set_engine(engine)
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    app.button(key="generate").click().run()
    assert app.session_state.wav is not None

    app.segmented_control(key="example").select("Shanti mantra").run()
    app.button(key="load_example").click().run()
    assert not app.exception
    assert app.text_area(key="text").value == SHANTI_MANTRA
    assert app.session_state.wav is None
    assert app.session_state.error is None

    app.button(key="generate").click().run()
    assert engine.calls[-1][0] == SHANTI_MANTRA
    assert app.session_state.download_name == "shanti_mantra.wav"


def test_page_upload_wins_and_a_bad_file_is_an_error():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    engine = FakeEngine()
    set_engine(engine)
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    app.file_uploader[0].upload("verse.txt", "ॐ नमः शिवाय ।\n".encode("utf-8"), "text/plain").run()
    app.button(key="generate").click().run()
    assert not app.exception
    assert engine.calls[-1][0] == "ॐ नमः शिवाय ।"
    assert app.session_state.download_name == "sanskrit_output.wav"
    assert any("verse.txt" in item.value for item in app.caption)

    app.file_uploader[0].set_value(("verse.txt", b"\xff", "text/plain")).run()
    app.button(key="generate").click().run()
    assert any("UTF-8" in item.value for item in app.error)
    assert app.session_state.wav is None
    assert not app.exception


def test_page_blank_description_uses_the_default_and_a_custom_one_is_kept():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    engine = FakeEngine()
    set_engine(engine)
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    app.text_area(key="description").set_value("   ").run()
    app.button(key="generate").click().run()
    assert engine.calls[-1][1] == DEFAULT_DESCRIPTION

    app.text_area(key="description").set_value("A clear female voice.").run()
    app.button(key="generate").click().run()
    assert engine.calls[-1][1] == "A clear female voice."
    assert not app.exception


def test_page_generation_failure_clears_the_player():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    set_engine(FakeEngine())
    app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    app.button(key="generate").click().run()
    assert app.session_state.wav is not None

    set_engine(FakeEngine(fail="network down"))
    app.button(key="generate").click().run()
    assert not app.exception
    assert any("network down" in item.value for item in app.error)
    assert app.session_state.wav is None
