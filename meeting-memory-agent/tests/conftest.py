from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def examples() -> Path:
    return ROOT / "examples" / "meetings"


@pytest.fixture
def history() -> Path:
    return ROOT / "examples" / "history"


@pytest.fixture
def questions_path() -> Path:
    return ROOT / "examples" / "questions.json"


@pytest.fixture
def history_questions() -> Path:
    return ROOT / "examples" / "history_questions.json"
