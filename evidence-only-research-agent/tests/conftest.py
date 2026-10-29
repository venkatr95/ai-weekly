from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

@pytest.fixture(scope="session")
def example_documents() -> Path:
    script = ROOT / "examples" / "build_sample_pdfs.py"
    subprocess.check_call([sys.executable, str(script)], cwd=ROOT)
    return ROOT / "examples" / "documents"
