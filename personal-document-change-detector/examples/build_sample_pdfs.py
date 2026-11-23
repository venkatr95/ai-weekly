"""Build simple PDF versions of the employment agreement examples."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "documents"


def main() -> None:
    import fitz

    for stem in ("employment_v1", "employment_v2"):
        source = DOCS / f"{stem}.md"
        target = DOCS / f"{stem}.pdf"
        text = source.read_text(encoding="utf-8")
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), text, fontsize=11)
        document.save(target)
        document.close()
        print(f"Wrote {target}")


if __name__ == "__main__":
    main()
