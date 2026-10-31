from __future__ import annotations

from pathlib import Path

import fitz


def write_text_pdf(path: Path, pages: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    try:
        for page_text in pages:
            page = document.new_page()
            y = 72
            for line in page_text.split("\n"):
                page.insert_text((72, y), line, fontsize=11, fontname="helv")
                y += 18
        document.save(path)
    finally:
        document.close()
