# Transcription

The default path does not invent speech. A recording is indexed only when a sidecar transcript sits beside it, or when you explicitly select a local speech-to-text provider.

## Sidecar transcripts

Give the transcript the same file name as the recording and one of these suffixes: `.vtt`, `.srt`, `.json`, `.txt`, `.md`, `.markdown`.

```text
notes/planning.mp3
notes/planning.txt
```

```bash
python cli.py import notes/planning.mp3
```

The recording is the source. The sidecar supplies the words, the speakers, and any timestamps. Supported audio suffixes are `.wav`, `.mp3`, `.m4a`, `.flac`, `.ogg`, `.webm`, and `.mp4`. This project does not shell out to FFmpeg. A format faster-whisper cannot decode will fail with a transcription error and will not be stored as a meeting.

## Optional local Whisper

```bash
pip install faster-whisper
```

Set `MEETING_TRANSCRIBER=whisper` or run `python cli.py transcribe notes/planning.mp3`. The model name is `MEETING_WHISPER_MODEL` (default `base`). The model runs on CPU. Segment start and end times are kept. Language and language probability are stored when the provider returns them. Segment confidence is stored from `avg_logprob` when that field is present.

Whisper does not identify people. If a segment arrives with a personal name, that name is replaced with `SPEAKER_NN`. Map the label yourself:

```bash
python cli.py speakers map "planning" --label SPEAKER_01 --name Alex
```

An empty transcript is a failure. The file is listed under failed inputs and is not indexed. A missing `faster-whisper` install returns an error that tells you to install it or add a sidecar. The error does not include the audio bytes.

## What this provider does not do

- It does not join a call or record a meeting. Record only with consent, outside this program.
- It does not recognize a person from their voice.
- It does not send audio to a cloud API.
- It does not translate. Multi-language text is whatever the selected provider emits, and the meeting `language` field stores the provider's language code when it has one.
- It does not log the transcript body. Failures name the file.

Pyannote is not bundled. A future diarizer must emit anonymous `SPEAKER_NN` labels. `diarization.coerce_diarization_label` enforces that boundary.

## Plain transcripts

`import` and `index` read TXT, Markdown, WebVTT, SRT, and JSON without a speech provider. Clock times become seconds. A line with no clock time keeps its line number. End times are stored only when the source has them. A header may set `Meeting`, `Date`, `Time`, `Participants`, and `Language`.
