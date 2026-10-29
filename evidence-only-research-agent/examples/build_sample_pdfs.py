"""Create the synthetic PDFs used by the demo and the gold-set evaluation.

The papers are fictional. They exist so the agent can be exercised without
shipping third-party research.
"""

from __future__ import annotations

from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent / "documents"

STUDY_A = [
    "\n".join(
        [
            "Rivera 2024",
            "Title: Morning light and sleep onset.",
            "Methods: Adults aged 25 to 40 years used Intervention X.",
            "The trial compared the program with a usual routine.",
        ]
    ),
    "\n".join(
        [
            "Results: Reported outcomes for sleep onset follow.",
            "The reported evidence supports the effectiveness of Intervention X.",
            "Intervention X produced a statistically significant improvement in sleep onset latency.",
            "In Rivera 2024 the primary outcome improved by 18 minutes.",
        ]
    ),
    "\n".join(
        [
            "Limitations of the Rivera 2024 trial are listed here.",
            "A reported limitation is the narrow age range of 25 to 40 years.",
            "A reported limitation is that follow-up lasted 6 weeks.",
            "Outcomes after 6 weeks were not measured.",
        ]
    ),
]

STUDY_B = [
    "\n".join(
        [
            "Okonkwo 2023",
            "Title: Pilot of Intervention X.",
            "The reported sample size in Okonkwo 2023 was 18 adults.",
        ]
    ),
    "\n".join(
        [
            "Results of the pilot trial are summarized here.",
            "Okonkwo 2023 reported a modest improvement in sleep onset latency.",
            "The authors describe the result as preliminary and not final.",
        ]
    ),
    "\n".join(
        [
            "Limitations of the pilot are listed here.",
            "A reported limitation is the sample size of 18 adults.",
            "The report says the sample is too small to establish effectiveness for Intervention X.",
        ]
    ),
]

STUDY_C = [
    "\n".join(
        [
            "Halvorsen 2024",
            "Title: Replication attempt for Intervention X.",
            "Methods: Adults used Intervention X for four weeks in this replication.",
        ]
    ),
    "\n".join(
        [
            "Results of the replication attempt are summarized here.",
            "Intervention X did not produce a statistically significant improvement in sleep onset latency.",
            "The primary outcome did not improve during the replication attempt.",
        ]
    ),
    "\n".join(
        [
            "Limitations of the replication are listed here.",
            "A reported limitation is that adherence was uneven across participants.",
        ]
    ),
]


def write_text_pdf(path: Path, pages: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    try:
        for page_text in pages:
            page = document.new_page()
            y = 72
            for line in page_text.split("\n"):
                if not line:
                    y += 16
                    continue
                page.insert_text((72, y), line, fontsize=11, fontname="helv")
                y += 18
        document.save(path)
    finally:
        document.close()


def write_scanned_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    try:
        page = document.new_page()
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 24, 24), 1)
        pixmap.clear_with(180)
        page.insert_image(fitz.Rect(72, 72, 220, 220), pixmap=pixmap)
        document.save(path)
    finally:
        document.close()


def main() -> None:
    write_text_pdf(ROOT / "study_a_rivera_2024.pdf", STUDY_A)
    write_text_pdf(ROOT / "study_b_okonkwo_2023.pdf", STUDY_B)
    write_text_pdf(ROOT / "study_c_halvorsen_2024.pdf", STUDY_C)
    write_scanned_pdf(ROOT / "scans" / "empty_scan.pdf")
    print(f"Wrote sample PDFs under {ROOT}")


if __name__ == "__main__":
    main()
