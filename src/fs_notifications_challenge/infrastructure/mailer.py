import logging
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlencode

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from fs_notifications_challenge.application.ports import PasswordResetMailer

logger = logging.getLogger("notifications.mailer")

TEMPLATES_DIR = Path(__file__).parent / "email_templates"
# autoescape for the .html template: the address goes into HTML, and so would anything
# else a template is given later
_templates = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))


def build_reset_url(frontend_url: str, token: str) -> str:
    return f"{frontend_url.rstrip('/')}/reset-password?{urlencode({'token': token})}"


def _human(minutes: int) -> str:
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour" + ("s" if hours != 1 else "")
    return f"{minutes} minutes"


class _ResetLinkMailer(PasswordResetMailer):
    """What both mailers share: turning (who, token) into a link and a message.
    Only HOW the message leaves the building differs."""

    def __init__(self, frontend_url: str, mail_from: str, expires_minutes: int) -> None:
        self._frontend_url = frontend_url
        self._from = mail_from
        self._expires_in = _human(expires_minutes)


    def build_message(self, to_email: str, token: str) -> EmailMessage:
        context = {"reset_url": build_reset_url(self._frontend_url, token), "expires_in": self._expires_in}
        message = EmailMessage()
        message["From"] = self._from
        message["To"] = to_email
        message["Subject"] = "Reset your password"
        message.set_content(_templates.get_template("password_reset.txt").render(context))
        
        message.add_alternative(_templates.get_template("password_reset.html").render(context), subtype="html")
        return message


class SmtpPasswordResetMailer(_ResetLinkMailer):
    def __init__(
            self,
            *,
            hostname: str, 
            port: int,
            username: str,
            password: str,
            start_tls: bool,
            frontend_url: str,
            mail_from: str, 
            expires_minutes: int,
        ) -> None:
        super().__init__(frontend_url, mail_from, expires_minutes)
        self._hostname = hostname
        self._port = port
        self._username = username
        self._password = password
        self._start_tls = start_tls


    async def send_reset_link(self, to_email: str, token: str) -> None:
        await aiosmtplib.send(
            self.build_message(to_email, token),
            hostname=self._hostname,
            port=self._port,
            username=self._username or None, 
            password=self._password or None,
            start_tls=self._start_tls,
        )


class ConsolePasswordResetMailer(_ResetLinkMailer):
    """Development stand-in: writes the link to the log instead of sending anything.
    Never use it where the log is shared; the link IS the password."""

    async def send_reset_link(self, to_email: str, token: str) -> None:
        logger.info(
            "Password reset link for %s (not emailed, MAIL_BACKEND=console): %s",
            to_email, build_reset_url(self._frontend_url, token),
        )