"""Email text is size-limited, and secret-shaped strings can be scrubbed from logs."""

import pytest

from email_to_action.errors import EmailActionError
from email_to_action.security import check_size, scrub


def test_oversized_email_is_rejected():
    with pytest.raises(EmailActionError):
        check_size("x" * 20, 10)


def test_scrub_redacts_key_shaped_text_without_changing_ordinary_words():
    cleaned = scrub("token-abcdEFGH1234 and the launch date is November 7.\napi_key=supersecret")
    assert "token-abcdEFGH1234" not in cleaned
    assert "supersecret" not in cleaned
    assert "November 7" in cleaned
