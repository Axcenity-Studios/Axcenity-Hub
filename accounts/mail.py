"""The development mailer: emails printed readably where runserver runs.

Django's console backend prints the raw MIME message, whose quoted-printable encoding
wraps long lines with a trailing ``=``, so a verification link arrives split in two and
can't be clicked or pasted. This backend prints the headers a reader needs and the
decoded plain-text body, then each link on its own line (an OSC 8 hyperlink when the
stream is a terminal, a plain URL otherwise; terminals such as VS Code's link both).
"""

import re

from django.core.mail.backends import console

URL = re.compile(r"https?://[^\s<>\"']+")
RULE = "-" * 79


def hyperlink(url):
    """``url`` as an OSC 8 terminal hyperlink whose visible text is the URL itself."""
    return f"\033]8;;{url}\033\\{url}\033]8;;\033\\"


class EmailBackend(console.EmailBackend):
    def write_message(self, message):
        msg = message.message()
        lines = [f"{name}: {msg[name]}" for name in ("Subject", "From", "To") if msg[name]]
        bodies = [
            part.get_content()
            for part in msg.walk()
            if part.get_content_type() == "text/plain" and not part.is_attachment()
        ]
        lines += ["", *(body.rstrip() for body in bodies)]
        links = list(dict.fromkeys(URL.findall("\n".join(bodies))))
        if links:
            linkify = hyperlink if self._is_terminal() else str
            lines += ["", "Links:", *(f"  {linkify(url)}" for url in links)]
        self.stream.write("\n".join(lines) + f"\n{RULE}\n")

    def _is_terminal(self):
        isatty = getattr(self.stream, "isatty", None)
        return bool(isatty and isatty())
