# Configuration

Settings come from the constructor, then from the environment, then from `.env` for variables that are not already set. A value passed to `Settings(...)` is not overwritten.

| Variable | Default | Meaning |
|---|---|---|
| `MEETING_INDEX_DIR` | `data/index` | Directory for `corpus.json`. |
| `MEETING_TRANSCRIBER` | `sidecar` | `sidecar` or `whisper`. |
| `MEETING_WHISPER_MODEL` | `base` | faster-whisper model name. Used only when the transcriber is `whisper`. |
| `MEETING_MAX_TEXT_BYTES` | `2000000` | Largest transcript that will be read. |
| `MEETING_MAX_AUDIO_BYTES` | `200000000` | Largest recording that will be accepted. |
| `MEETING_RETENTION_DAYS` | unset | Drop dated meetings older than this many days on the next ingest. |

`--index-dir` on the CLI overrides `MEETING_INDEX_DIR` for that command. `evaluate` uses a temporary index unless you pass `--index-dir`, so a score run does not rewrite your working index.

## Deadline rules

These are code rules, not configuration.

- `2026-03-20` and `March 20, 2026` are explicit calendar days.
- `March 20` uses the meeting year. If that day is before the meeting, the next year is used. This applies to a new deadline ("by March 20"), not to the old one.
- `instead of March 20` and `from March 20 to March 27` keep the meeting year for the old date.
- `Friday` is the next Friday, including today when the meeting is on Friday. `next Friday` is the Friday after that.
- `next week` is seven days after the meeting date.
- `tomorrow` is the next day. `today` and `tonight` are the meeting date.
- A weekday, "tomorrow", "next week", or a month and day with no meeting date stays unresolved. The original words are kept and no ISO date is stored.
- `before the next release` is an event deadline. `by 5pm` is a clock time. Neither becomes an ISO date.
- A transcript line with no end time does not get one.
