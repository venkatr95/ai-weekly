"""Whitespace, signatures, disclaimers, and quoted lines stay out of the action text."""

from email_to_action.preprocessor import prepare_body, split_signature


def test_signature_and_disclaimer_leave_the_request():
    body = "\n".join(
        [
            "Hi Alex,",
            "",
            "Please send the screenshots by November 7.",
            "",
            "Thanks,",
            "Sarah",
            "",
            "This email is confidential and intended only for the recipient.",
        ]
    )
    content, _quoted, signature, greeting = prepare_body(body)
    assert "Please send the screenshots by November 7." in content
    assert "Sarah" not in content
    assert "confidential" not in content.lower()
    assert "Thanks" in signature
    assert greeting == "Alex"


def test_quote_lines_are_separated_from_new_text():
    body = "Bumping this.\n> Please send the old file by Monday."
    content, quoted, _signature, _greeting = prepare_body(body)
    assert content == "Bumping this."
    assert "old file" in quoted
    assert ">" not in quoted


def test_closing_inside_a_sentence_is_not_a_signature():
    content, signature = split_signature("Thanks for the context. Please send the file by Friday.")
    assert signature == ""
    assert "Please send the file" in content
