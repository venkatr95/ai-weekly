"""Thread parsing keeps headers, order, and quoted history."""

from email.message import EmailMessage as MimeMessage

from email_to_action.parser import parse_eml, parse_text


LAUNCH = """\
From: Sarah
Subject: Q4 Product Launch

Hi Alex,

We need to finalize the product launch materials.

Could you please:
- Complete the landing page by November 10.

Thanks,
Sarah
"""


def test_single_message_headers_greeting_and_signature():
    messages, warnings = parse_text(LAUNCH)
    assert warnings == []
    assert len(messages) == 1
    message = messages[0]
    assert message.message_id == "message-1"
    assert message.sender_name == "Sarah"
    assert message.subject == "Q4 Product Launch"
    assert message.addressee_name == "Alex"
    assert message.addressee_ambiguous is False
    assert "Complete the landing page by November 10." in message.body
    assert "Thanks" not in message.body
    assert "Sarah" not in message.body


def test_original_message_marker_is_oldest_first():
    thread = """\
From: Alex Rivera
To: Sarah Chen
Date: Tue, 04 Nov 2026 09:00:00 -0500
Subject: Re: Q4 Product Launch

The screenshots went out yesterday.

-----Original Message-----
From: Sarah Chen
To: Alex Rivera
Date: Mon, 03 Nov 2026 09:00:00 -0500
Subject: Q4 Product Launch

Hi Alex,

Could you please send the screenshots by November 7?

Thanks,
Sarah
"""
    messages, _warnings = parse_text(thread)
    assert [message.sender_name for message in messages] == ["Sarah Chen", "Alex Rivera"]
    assert messages[0].message_id == "message-1"
    assert "send the screenshots" in messages[0].body
    assert "went out" in messages[1].body
    assert "send the screenshots" not in messages[1].body


def test_on_wrote_block_becomes_the_earlier_message():
    thread = """\
From: Alex
Date: Tue, 04 Nov 2026 09:00:00 -0500
To: Sarah
Subject: Re: Notes

Sounds good.

On Mon, 03 Nov 2026, Sarah wrote:
Hi Alex,

Please send the notes by Friday.

Thanks,
Sarah
"""
    messages, _warnings = parse_text(thread)
    assert len(messages) == 2
    assert messages[0].sender_name == "Sarah"
    assert "Please send the notes by Friday." in messages[0].body
    assert messages[1].body == "Sounds good."


def test_quoted_header_block_is_lifted_into_an_earlier_message():
    thread = """\
From: Alex
To: Sarah
Date: Tue, 04 Nov 2026 09:00:00 -0500
Subject: Re: Notes

Bumping this.

> From: Sarah
> To: Alex
> Date: Mon, 03 Nov 2026 09:00:00 -0500
> Subject: Notes
>
> Please send the notes.
"""
    messages, warnings = parse_text(thread)
    assert [message.sender_name for message in messages] == ["Sarah", "Alex"]
    assert "Please send the notes." in messages[0].body
    assert "Please send the notes." not in messages[1].body
    assert not any("Quoted lines" in warning for warning in warnings)


def test_bare_quote_lines_stay_out_of_the_new_message():
    thread = """\
From: Alex
To: Sarah
Subject: Re: Notes

Bumping this.
> Please send the old file by Monday.
"""
    messages, warnings = parse_text(thread)
    assert len(messages) == 1
    assert messages[0].body == "Bumping this."
    assert "old file" in messages[0].quoted_text
    assert any("Quoted lines" in warning for warning in warnings)


def test_eml_round_trip_uses_headers_and_plain_body():
    mime = MimeMessage()
    mime["From"] = "Sarah <sarah@example.com>"
    mime["To"] = "Alex <alex@example.com>"
    mime["Subject"] = "Q4 Product Launch"
    mime["Date"] = "Mon, 02 Nov 2026 09:00:00 -0500"
    mime.set_content("Hi Alex,\n\nPlease send the screenshots by November 7.\n")
    messages, warnings = parse_eml(mime.as_bytes())
    assert warnings == []
    assert len(messages) == 1
    message = messages[0]
    assert message.sender_name == "Sarah"
    assert message.sender_email == "sarah@example.com"
    assert message.addressee_name == "Alex"
    assert message.to[0].email == "alex@example.com"
    assert "Please send the screenshots by November 7." in message.body
    assert message.date_iso is not None
    assert message.date_iso.startswith("2026-11-02")


def test_multiple_recipients_stay_ambiguous_without_a_greeting():
    thread = """\
From: Sarah
To: Alex, Jordan
Subject: Launch

Please send the screenshots by November 7.
"""
    messages, _warnings = parse_text(thread)
    assert messages[0].addressee_name is None
    assert messages[0].addressee_ambiguous is True


def test_greeting_can_name_the_addressee_when_to_is_missing():
    messages, _warnings = parse_text("Hi Priya,\n\nPlease send the report by Friday.\n")
    assert messages[0].addressee_name == "Priya"
    assert messages[0].sender_name is None
