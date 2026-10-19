import logging

from fastapi import BackgroundTasks

from fs_notifications_challenge.application.ports import PasswordResetMailer

logger = logging.getLogger("notifications.mailer")


class BackgroundMailer(PasswordResetMailer):
    """Send through another mailer once the HTTP response has gone out.
    
    Two reasons. SMTP is slow, and a request that takes longer when the email exists
    tells the caller which emails have accounts. And a mail server that is down must 
    not turn "we send you instructions" into a 500. The use case does not know this 
    happens: it just calls a PasswordResetMailer."""

    def __init__(self, mailer: PasswordResetMailer, background_tasks: BackgroundTasks) -> None:
        self._mailer = mailer
        self._background_tasks = background_tasks


    async def send_reset_link(self, to_email: str, token: str) -> None:
        self._background_tasks.add_task(self._send, to_email, token)


    async def _send(self, to_email: str, token: str) -> None:
        try:
            await self._mailer.send_reset_link(to_email, token)
        except Exception:  # noqa: BLE001 - nobody is waiting for this response any more
            logger.exception("Could not send the password reset email to %s", to_email)