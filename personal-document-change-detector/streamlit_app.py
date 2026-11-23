"""Web UI for the Personal Document Change Detector. Run with: streamlit run streamlit_app.py"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from document_detector.config import IMPORTANCE_RANK, load_settings
from document_detector.errors import DetectorError
from document_detector.pipeline import compare
from document_detector.report_generator import render_json, render_markdown
from document_detector.schemas import CATEGORY_LABELS, IMPORTANCE_LABELS, ComparisonReport

EXAMPLES = {
    "Employment agreement": (
        ROOT / "examples" / "documents" / "employment_v1.md",
        ROOT / "examples" / "documents" / "employment_v2.md",
    ),
    "Supplier terms": (
        ROOT / "examples" / "documents" / "supplier_v1.md",
        ROOT / "examples" / "documents" / "supplier_v2.md",
    ),
}


def compare_paths(
    old_path: Path,
    new_path: Path,
    *,
    provider: str,
    min_importance: str,
    include_formatting: bool,
) -> ComparisonReport:
    settings = load_settings(provider)
    return compare(
        old_path,
        new_path,
        settings=settings,
        min_importance=min_importance,
        include_formatting=include_formatting,
    )


def compare_uploads(
    old_name: str,
    old_data: bytes,
    new_name: str,
    new_data: bytes,
    *,
    provider: str,
    min_importance: str,
    include_formatting: bool,
) -> ComparisonReport:
    old_path = _temp_file(old_name, old_data)
    new_path = _temp_file(new_name, new_data)
    try:
        return compare_paths(
            old_path,
            new_path,
            provider=provider,
            min_importance=min_importance,
            include_formatting=include_formatting,
        )
    finally:
        old_path.unlink(missing_ok=True)
        new_path.unlink(missing_ok=True)


def change_rows(report: ComparisonReport) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for change in sorted(report.changes, key=lambda c: (-IMPORTANCE_RANK[c.importance], c.change_id)):
        rows.append(
            {
                "ID": change.change_id,
                "Section": change.section or "—",
                "Type": change.change_type,
                "Importance": IMPORTANCE_LABELS[change.importance],
                "Categories": ", ".join(CATEGORY_LABELS.get(c, c) for c in change.categories),
                "Previous": _short(change.previous_text),
                "Updated": _short(change.updated_text),
            }
        )
    return rows


def _short(value: str | None, limit: int = 80) -> str:
    if not value:
        return "—"
    text = " ".join(value.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _temp_file(name: str, data: bytes) -> Path:
    suffix = Path(name).suffix or ".txt"
    handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    handle.write(data)
    handle.close()
    return Path(handle.name)


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Document Change Detector", page_icon="📄", layout="wide")
    st.title("Personal Document Change Detector")
    st.caption(
        "Compare two document versions. Deterministic diffs find what changed; "
        "explanations are clearly labeled as interpretations, not legal advice."
    )

    with st.sidebar:
        st.header("Options")
        provider = st.selectbox("Provider", ["heuristic", "xai"], index=0)
        min_importance = st.selectbox(
            "Minimum importance",
            list(IMPORTANCE_RANK.keys()),
            index=0,
            format_func=lambda key: IMPORTANCE_LABELS[key],
        )
        include_formatting = st.checkbox("Include formatting-only changes", value=False)
        example_name = st.selectbox("Load example", ["(none)", *EXAMPLES.keys()])

    tab_upload, tab_example = st.tabs(["Upload two files", "Use example"])
    report: ComparisonReport | None = None

    with tab_upload:
        col_old, col_new = st.columns(2)
        with col_old:
            old_file = st.file_uploader("Previous version", type=["pdf", "docx", "txt", "md"], key="old")
        with col_new:
            new_file = st.file_uploader("Updated version", type=["pdf", "docx", "txt", "md"], key="new")
        if st.button("Compare uploads", type="primary", disabled=not (old_file and new_file)):
            try:
                report = compare_uploads(
                    old_file.name,
                    old_file.getvalue(),
                    new_file.name,
                    new_file.getvalue(),
                    provider=provider,
                    min_importance=min_importance,
                    include_formatting=include_formatting,
                )
            except DetectorError as exc:
                st.error(str(exc))

    with tab_example:
        if example_name != "(none)":
            old_path, new_path = EXAMPLES[example_name]
            st.write(f"Previous: `{old_path.name}`")
            st.write(f"Updated: `{new_path.name}`")
            if st.button("Compare example", type="primary"):
                try:
                    report = compare_paths(
                        old_path,
                        new_path,
                        provider=provider,
                        min_importance=min_importance,
                        include_formatting=include_formatting,
                    )
                except DetectorError as exc:
                    st.error(str(exc))
        else:
            st.info("Choose an example in the sidebar, or upload two files.")

    if report is None:
        return

    summary = report.summary
    st.subheader(f"{summary.total_changes} changes detected")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Added", summary.added)
    m2.metric("Removed", summary.removed)
    m3.metric("Modified", summary.modified)
    m4.metric("High+", summary.critical + summary.high)
    m5.metric("Provider", report.provider)

    st.dataframe(change_rows(report), use_container_width=True, hide_index=True)

    st.markdown("### Recommended review priorities")
    for item in report.review_recommendations:
        st.markdown(f"- {item}")

    with st.expander("Detailed changes"):
        for change in report.changes:
            st.markdown(f"**{change.change_id}: {change.title}** ({IMPORTANCE_LABELS[change.importance]})")
            st.markdown(f"- Explanation: {change.explanation}")
            st.markdown(f"- Impact: {change.impact}")
            cols = st.columns(2)
            cols[0].text_area("Previous", change.previous_text or "(none)", height=120, key=f"p-{change.change_id}")
            cols[1].text_area("Updated", change.updated_text or "(none)", height=120, key=f"u-{change.change_id}")

    st.info(report.disclaimer)

    c1, c2 = st.columns(2)
    c1.download_button("Download Markdown", render_markdown(report), file_name="comparison.md")
    c2.download_button("Download JSON", render_json(report), file_name="comparison.json")

    if report.warnings:
        st.warning("\n".join(report.warnings))


if __name__ == "__main__":
    main()
