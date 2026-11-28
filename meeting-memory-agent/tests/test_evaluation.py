from pathlib import Path

from meeting_memory.config import Settings
from meeting_memory.evaluation import evaluate, load_questions
from meeting_memory.pipeline import MeetingMemory


def test_bundled_questions_pass(tmp_path: Path, examples: Path, questions_path: Path):
    memory = MeetingMemory(Settings(index_dir=tmp_path / "index"))
    memory.ingest(examples)
    report = evaluate(memory, load_questions(questions_path))
    failed = [score for score in report.scores if not score.passed]
    details = "\n".join(
        f"{score.id}: {', '.join(score.failures)}" for score in failed
    )
    assert report.all_passed, details


def test_history_questions_still_pass(tmp_path: Path, history: Path, history_questions: Path):
    memory = MeetingMemory(Settings(index_dir=tmp_path / "index"))
    memory.ingest(history)
    report = evaluate(memory, load_questions(history_questions))
    failed = [score for score in report.scores if not score.passed]
    details = "\n".join(f"{score.id}: {', '.join(score.failures)}" for score in failed)
    assert report.all_passed, details
