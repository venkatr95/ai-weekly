"""Web UI for Sanskrit TTS. Run with: streamlit run streamlit_app.py"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from sanskrit_tts_core import (
    DEFAULT_DESCRIPTION,
    EXAMPLES,
    GANESHA_SLOKA,
    MAX_TEXT_CHARS,
    TTSError,
    get_engine,
    normalize_description,
    normalize_text,
)

MAX_UPLOAD_BYTES = 64 * 1024
DOWNLOAD_NAMES = {
    "Ganesha sloka": "ganesha_sloka.wav",
    "Shanti mantra": "shanti_mantra.wav",
}


@st.cache_resource(max_entries=4, show_spinner=False)
def load_tts_engine(engine_id: int):
    """Load one Indic Parler-TTS model for this process.

    engine_id is the cache key. Replacing the engine, as tests do, loads
    that object instead of reusing the previous one. A normal session keeps
    the same id, so later reruns do not download the model again.
    """

    engine = get_engine()
    if id(engine) != engine_id:
        raise TTSError("The speech model changed while it was loading. Generate again.")
    return engine.load()


def output_name(text: str) -> str:
    """WAV name for a known example. Edited text uses sanskrit_output.wav."""

    stripped = text.strip()
    for label, sample in EXAMPLES.items():
        if stripped == sample:
            return DOWNLOAD_NAMES[label]
    return "sanskrit_output.wav"


def read_upload(name: str, data: bytes) -> str:
    """UTF-8 text from an upload. The name is not opened as a path."""

    filename = Path(str(name).replace("\\", "/")).name
    if not filename or filename in {".", ".."}:
        raise TTSError("The uploaded file has no file name.")
    if Path(filename).suffix.lower() != ".txt":
        raise TTSError("Upload a .txt file of Devanāgarī text.")
    if not data:
        raise TTSError("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise TTSError("The uploaded file is larger than 64 KB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TTSError("The uploaded file is not UTF-8 text.") from exc
    return normalize_text(text)


def public_error(exc: BaseException) -> str:
    """Short error text for the page."""

    text = str(exc).strip() or exc.__class__.__name__
    if len(text) > 500:
        text = text[:500] + "..."
    return text


def synthesize(text: str, description: str, engine=None):
    """Validate, then generate. An empty box does not load the model."""

    cleaned = normalize_text(text)
    voice = normalize_description(description)
    if engine is None:
        engine = load_tts_engine(id(get_engine()))
    return engine.generate(cleaned, voice)


def main() -> None:
    st.set_page_config(page_title="Sanskrit TTS", page_icon="ॐ", layout="wide")
    _init_state()

    st.title("Sanskrit TTS")
    st.caption(
        "Paste Sanskrit in Devanāgarī. Indic Parler-TTS reads it on this machine. "
        "The first generation downloads the model. The text is not rewritten."
    )

    with st.sidebar:
        st.header("Voice")
        st.text_area(
            "Voice description",
            key="description",
            height=280,
            max_chars=MAX_TEXT_CHARS,
            help="English style prompt. A blank description uses the measured, reverent default.",
        )
        st.caption("CUDA is used when it is available. Otherwise generation runs on CPU.")
        st.header("Example")
        st.segmented_control(
            "Example",
            list(EXAMPLES),
            key="example",
            required=True,
            width="stretch",
        )
        st.button(
            "Load example",
            key="load_example",
            icon=":material/menu_book:",
            on_click=_load_example,
        )

    st.text_area(
        "Sanskrit text",
        key="text",
        height=200,
        max_chars=MAX_TEXT_CHARS,
        placeholder="Paste Devanāgarī here",
        help="Devanāgarī, including daṇḍa and verse breaks. The text is spoken as written.",
    )
    uploaded = st.file_uploader(
        "Upload a .txt file",
        type=["txt"],
        key=f"upload-{st.session_state.upload_generation}",
        help="An uploaded file is read instead of the text box.",
    )
    if uploaded is not None:
        st.caption(f"Generate reads {Path(uploaded.name).name} instead of the text box.")

    if st.button(
        "Generate recitation",
        type="primary",
        key="generate",
        icon=":material/graphic_eq:",
    ):
        try:
            if uploaded is not None:
                source = read_upload(uploaded.name, uploaded.getvalue())
                note = f"Read {Path(uploaded.name).name}."
            else:
                source = st.session_state.text
                note = "Read the text box."
            with st.spinner("Generating the recitation. The first run downloads the model."):
                clip = synthesize(source, st.session_state.description)
        except TTSError as exc:
            st.session_state.wav = None
            st.session_state.error = str(exc)
            st.session_state.status_note = None
        except Exception as exc:
            st.session_state.wav = None
            st.session_state.error = f"Could not generate audio. {public_error(exc)}"
            st.session_state.status_note = None
        else:
            st.session_state.wav = clip.wav_bytes()
            st.session_state.download_name = output_name(source)
            st.session_state.error = None
            st.session_state.status_note = note

    if st.session_state.error:
        st.error(st.session_state.error)
        return

    wav = st.session_state.wav
    if wav is None:
        return

    st.success("Recitation ready.")
    if st.session_state.status_note:
        st.caption(st.session_state.status_note)
    st.audio(wav, format="audio/wav", alt="Sanskrit recitation")
    st.download_button(
        "Download WAV",
        data=wav,
        file_name=st.session_state.download_name,
        mime="audio/wav",
        key="download_wav",
        icon=":material/download:",
    )


def _init_state() -> None:
    if "text" not in st.session_state:
        st.session_state.text = GANESHA_SLOKA
    if "description" not in st.session_state:
        st.session_state.description = DEFAULT_DESCRIPTION
    if "example" not in st.session_state:
        st.session_state.example = "Ganesha sloka"
    if "upload_generation" not in st.session_state:
        st.session_state.upload_generation = 0
    if "wav" not in st.session_state:
        st.session_state.wav = None
    if "error" not in st.session_state:
        st.session_state.error = None
    if "download_name" not in st.session_state:
        st.session_state.download_name = "ganesha_sloka.wav"
    if "status_note" not in st.session_state:
        st.session_state.status_note = None


def _load_example() -> None:
    label = st.session_state.example
    st.session_state.text = EXAMPLES[label]
    st.session_state.upload_generation += 1
    st.session_state.wav = None
    st.session_state.error = None
    st.session_state.status_note = None


def _running_as_streamlit_script() -> bool:
    if __name__ == "__main__":
        return True
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except ImportError:
        return False
    try:
        return get_script_run_ctx(suppress_warning=True) is not None
    except TypeError:
        return get_script_run_ctx() is not None


if _running_as_streamlit_script():
    main()
