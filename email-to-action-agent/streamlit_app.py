"""Web UI for the Email-to-Action Agent. Run with: streamlit run streamlit_app.py"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from email_to_action.errors import EmailActionError
from email_to_action.pipeline import analyze
from email_to_action.report import render_json, render_markdown, to_public
from email_to_action.schemas import ActionList, PublicDeadline

TONES = ("professional", "friendly", "concise", "formal")
EXAMPLES = {
    "Launch thread": ROOT / "examples" / "launch_thread.txt",
    "Single email": ROOT / "examples" / "email.txt",
    "Email thread": ROOT / "examples" / "email_thread.txt",
}
_EVENT_OTHER = re.compile(r"\b(these|those|remaining|other)\b", re.IGNORECASE)


def prepare_text(text: str) -> str:
    """Keep pasted text from being read as a file path.

    analyze() treats a single line as a path when that file exists. A trailing
    newline keeps a one-line paste on the email-text path.
    """
    if "\n" not in text and "\r" not in text:
        return text + "\n"
    return text


def analyze_text(
    text: str,
    *,
    received_at: str | None,
    tone: str,
    include_reply: bool,
) -> ActionList:
    if not text.strip():
        raise EmailActionError("Email text is empty.")
    return analyze(
        prepare_text(text),
        received_at=received_at,
        tone=tone,
        include_reply=include_reply,
    )


def analyze_upload(
    name: str,
    data: bytes,
    *,
    received_at: str | None,
    tone: str,
    include_reply: bool,
) -> ActionList:
    if Path(name).suffix.lower() == ".eml":
        with tempfile.NamedTemporaryFile(suffix=".eml", delete=False) as handle:
            handle.write(data)
            path = Path(handle.name)
        try:
            return analyze(path, received_at=received_at, tone=tone, include_reply=include_reply)
        finally:
            path.unlink(missing_ok=True)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EmailActionError("The uploaded file is not UTF-8 text. Use a .txt or .eml file.") from exc
    return analyze_text(text, received_at=received_at, tone=tone, include_reply=include_reply)


def deadline_label(deadline: PublicDeadline | None) -> str:
    if deadline is None:
        return "Not specified"
    wording = deadline.original_text or "Not specified"
    if deadline.type == "unresolved":
        return f"{wording} (unresolved)"
    if deadline.precision == "event" and _EVENT_OTHER.search(wording):
        return "After other tasks"
    return wording


def status_label(status: str) -> str:
    if status == "pending":
        return "Pending"
    return status.replace("_", " ").title()


def action_rows(action: ActionList) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in to_public(action).actions:
        normalized = ""
        if item.deadline is not None and item.deadline.normalized_date:
            normalized = item.deadline.normalized_date
        rows.append(
            {
                "Task": item.task_id,
                "Description": item.description,
                "Owner": item.owner or "Unassigned",
                "Deadline": deadline_label(item.deadline),
                "Normalized": normalized,
                "Priority": item.priority.title(),
                "Status": status_label(item.status),
            }
        )
    return rows


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Email-to-Action Agent", page_icon="✉️", layout="wide")
    _init_state()

    st.title("Email-to-Action Agent")
    st.caption(
        "Paste an email or a thread. The page extracts tasks, owners, deadlines, and a draft reply. "
        "Email stays on this machine. The draft is not sent."
    )

    with st.sidebar:
        st.header("Options")
        st.selectbox("Tone", TONES, key="tone", help="Wording of the draft. The draft stays a draft.")
        st.text_input(
            "Received at",
            key="received_at",
            placeholder="2026-11-01T09:00:00+01:00",
            help="ISO-8601 timestamp used only when a message has no Date header.",
        )
        st.checkbox(
            "Include draft reply",
            key="include_reply",
            help="Leave this off to extract actions without a draft.",
        )
        st.header("Example")
        st.selectbox("Sample email", list(EXAMPLES), key="example")
        if st.button("Load example", key="load_example"):
            st.session_state.email_text = EXAMPLES[st.session_state.example].read_text(encoding="utf-8")
            st.session_state.upload_generation += 1

    email_text = st.text_area("Email", key="email_text", height=280)
    uploaded = st.file_uploader(
        "Upload a .txt or .eml file",
        type=["txt", "eml"],
        key=f"upload-{st.session_state.upload_generation}",
        help="An uploaded file is used instead of the text box.",
    )
    if uploaded is not None:
        st.caption(f"Analyze will read {uploaded.name}. Load an example, or upload nothing, to use the text box.")

    if st.button("Analyze", type="primary", key="analyze"):
        received_at = st.session_state.received_at.strip() or None
        try:
            if uploaded is not None:
                action = analyze_upload(
                    uploaded.name,
                    uploaded.getvalue(),
                    received_at=received_at,
                    tone=st.session_state.tone,
                    include_reply=st.session_state.include_reply,
                )
                st.session_state.input_note = f"Analyzed uploaded file {uploaded.name}."
            else:
                action = analyze_text(
                    email_text,
                    received_at=received_at,
                    tone=st.session_state.tone,
                    include_reply=st.session_state.include_reply,
                )
                st.session_state.input_note = "Analyzed the pasted email."
        except EmailActionError as exc:
            st.session_state.action = None
            st.session_state.error = str(exc)
        else:
            st.session_state.action = action
            st.session_state.error = None
            draft = action.draft_reply
            st.session_state.draft_subject = draft.subject or "" if draft else ""
            st.session_state.draft_body = draft.body if draft else ""

    if st.session_state.error:
        st.error(st.session_state.error)

    action = st.session_state.action
    if action is None:
        return

    st.caption(st.session_state.input_note)
    _render_result(action)


def _init_state() -> None:
    import streamlit as st

    if "email_text" not in st.session_state:
        st.session_state.email_text = EXAMPLES["Launch thread"].read_text(encoding="utf-8")
    if "tone" not in st.session_state:
        st.session_state.tone = "professional"
    if "received_at" not in st.session_state:
        st.session_state.received_at = ""
    if "include_reply" not in st.session_state:
        st.session_state.include_reply = True
    if "example" not in st.session_state:
        st.session_state.example = "Launch thread"
    if "upload_generation" not in st.session_state:
        st.session_state.upload_generation = 0
    if "action" not in st.session_state:
        st.session_state.action = None
    if "error" not in st.session_state:
        st.session_state.error = None
    if "input_note" not in st.session_state:
        st.session_state.input_note = ""
    if "draft_subject" not in st.session_state:
        st.session_state.draft_subject = ""
    if "draft_body" not in st.session_state:
        st.session_state.draft_body = ""


def _render_result(action: ActionList) -> None:
    import streamlit as st

    report = to_public(action)
    meta = report.email_metadata
    st.subheader("Summary")
    st.write(report.summary)
    columns = st.columns(3)
    columns[0].metric("Subject", meta.subject or "Not specified")
    columns[1].metric("Sender", meta.sender or "Not specified")
    columns[2].metric("Received at", meta.received_at or "Not specified")
    if action.participants:
        labels = ", ".join(_participant_label(person) for person in action.participants)
        st.caption(f"Participants: {labels}")

    actions_tab, reply_tab, report_tab = st.tabs(["Actions", "Draft reply", "Report"])
    with actions_tab:
        _render_actions(action)
    with reply_tab:
        _render_reply(action)
    with report_tab:
        st.markdown(render_markdown(action))
        st.download_button(
            "Download Markdown",
            data=render_markdown(action) + "\n",
            file_name="actions.md",
            mime="text/markdown",
            key="download_md",
        )
        st.download_button(
            "Download JSON",
            data=render_json(action) + "\n",
            file_name="actions.json",
            mime="application/json",
            key="download_json",
        )
        st.caption("The downloads are the validated report. An edit in the draft tab is not written into them.")


def _render_actions(action: ActionList) -> None:
    import streamlit as st

    report = to_public(action)
    rows = action_rows(action)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.info("No actions were extracted.")

    st.subheader("Questions")
    if report.questions:
        for question in report.questions:
            owner = f" ({question.owner})" if question.owner else ""
            st.markdown(f"**{question.question_id}**{owner}: {question.text}")
    else:
        st.write("None.")

    st.subheader("Dependencies")
    linked = [item for item in report.actions if item.dependencies]
    if linked:
        for item in linked:
            deps = ", ".join(item.dependencies)
            st.markdown(f"**{item.task_id}** depends on {deps}.")
    else:
        st.write("None.")

    st.subheader("Commitments")
    if action.commitments:
        for item in action.commitments:
            when = "not specified"
            if item.deadline is not None and item.deadline.original_wording:
                when = item.deadline.original_wording
            st.markdown(f"**{item.made_by or 'A participant'}:** {item.description} Deadline: {when}.")
    else:
        st.write("None.")

    st.subheader("Priority notes")
    if report.actions:
        for item in report.actions:
            st.markdown(f"**{item.task_id}:** {item.priority_explanation}")
    else:
        st.write("None.")

    st.subheader("Uncertainties")
    if report.uncertainties:
        for item in report.uncertainties:
            st.markdown(f"- {item}")
    else:
        st.write("None.")

    with st.expander("Source lines"):
        if report.actions:
            for item in report.actions:
                st.markdown(f"**{item.task_id}:** {item.evidence}")
        else:
            st.write("None.")
        for source in report.source_references:
            sender = source.sender or "Unknown sender"
            subject = source.subject or "No subject"
            when = source.date or "no timestamp"
            st.caption(f"{source.message_id}: {sender}, {subject}, {when}")


def _render_reply(action: ActionList) -> None:
    import streamlit as st

    if action.draft_reply is None:
        st.info("No reply was requested. A reply is never sent without explicit approval.")
        return
    st.caption("Edit the draft here. This page does not send email.")
    st.text_input("Subject", key="draft_subject")
    st.text_area("Body", key="draft_body", height=280)
    edited = f"Subject: {st.session_state.draft_subject}\n\n{st.session_state.draft_body}\n"
    st.download_button(
        "Download edited draft",
        data=edited,
        file_name="draft-reply.txt",
        mime="text/plain",
        key="download_draft",
    )
    st.caption(f"Tone: {action.draft_reply.tone}. The draft requires approval and does not accept the work.")


def _participant_label(person) -> str:
    if person.name and person.email:
        label = f"{person.name} <{person.email}>"
    else:
        label = person.name or person.email or "Unknown"
    return f"{label} ({person.role})"


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
