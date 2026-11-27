"""The development mailer prints emails readably, links whole."""

import io

from django.core.mail import EmailMultiAlternatives

from accounts.mail import EmailBackend, hyperlink

LINK = "http://127.0.0.1:8000/accounts/confirm-email/OA:1xWyZx:6_aT95Zgc7FHjlU7nB-urhdy0MqWXvavdPQE8u9XDhY/"


class Terminal(io.StringIO):
    def isatty(self):
        return True


def send(stream):
    message = EmailMultiAlternatives(
        "[Axcenity Hub] Please Confirm Your Email Address",
        f"Hello from Axcenity Hub — café!\n\nTo confirm this is correct, go to {LINK}\n",
        "Axcenity Hub <noreply@localhost>",
        ["member@example.com"],
    )
    message.attach_alternative(f'<a href="{LINK}">Confirm</a>', "text/html")
    EmailBackend(stream=stream).send_messages([message])
    return stream.getvalue()


def test_a_long_link_prints_whole_with_the_body_decoded():
    out = send(io.StringIO())
    assert "Subject: [Axcenity Hub] Please Confirm Your Email Address" in out
    assert "To: member@example.com" in out
    assert "café" in out  # decoded, not =C3=A9
    assert f"go to {LINK}\n" in out
    assert f"Links:\n  {LINK}\n" in out  # once, though the HTML part repeats it
    assert "=\n" not in out and "<a href" not in out and "\033" not in out


def test_a_terminal_gets_the_link_as_a_hyperlink():
    out = send(Terminal())
    assert f"  {hyperlink(LINK)}\n" in out
    assert hyperlink(LINK) == f"\033]8;;{LINK}\033\\{LINK}\033]8;;\033\\"
