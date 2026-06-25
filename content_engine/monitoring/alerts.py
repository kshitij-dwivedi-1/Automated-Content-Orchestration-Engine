"""Async Slack and email alerting."""

from __future__ import annotations

from datetime import UTC, datetime
from email.message import EmailMessage

import aiohttp
import aiosmtplib
import structlog

from content_engine.config.settings import Settings
from content_engine.constants import ALERT_TIMEOUT_SECONDS, MSG_ALERT_SUBJECT


class AlertManager:
    """Send pipeline failure alerts to configured destinations."""

    def __init__(self, settings: Settings, logger: structlog.BoundLogger | None = None) -> None:
        """Initialize the alert manager.

        Args:
            settings: Application settings.
            logger: Optional structured logger.
        """

        self.settings = settings
        self.logger = logger or structlog.get_logger(__name__)

    async def alert(self, task_id: int | str, stage: str, error_message: str, severity: str) -> None:
        """Send alert notifications for a failed task stage.

        Args:
            task_id: Failed task identifier.
            stage: Failed pipeline stage.
            error_message: Error details.
            severity: Severity level.

        Returns:
            None.
        """

        payload = {
            "task_id": task_id,
            "stage": stage,
            "error": error_message,
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": severity,
        }
        message = (
            f"{MSG_ALERT_SUBJECT}\n"
            f"Task: {task_id}\nStage: {stage}\nSeverity: {severity}\n"
            f"Error: {error_message}\nTimestamp: {payload['timestamp']}"
        )
        await self._send_slack(message, payload)
        await self._send_email(message)

    async def _send_slack(self, text: str, payload: dict[str, object]) -> None:
        """Send Slack webhook notification.

        Args:
            text: Human-readable alert text.
            payload: Structured alert payload.

        Returns:
            None.
        """

        if not self.settings.SLACK_WEBHOOK_URL:
            return
        try:
            timeout = aiohttp.ClientTimeout(total=ALERT_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.settings.SLACK_WEBHOOK_URL, json={"text": text, "metadata": payload}) as response:
                    if response.status >= 400:
                        self.logger.warning("slack_alert_failed", status=response.status, body=await response.text())
        except Exception as exc:
            self.logger.warning("slack_alert_error", error=str(exc))

    async def _send_email(self, text: str) -> None:
        """Send SMTP email notification.

        Args:
            text: Email body text.

        Returns:
            None.
        """

        smtp = self.settings.SMTP_CONFIG
        if not self.settings.ALERT_EMAIL or not smtp.host or not smtp.sender:
            return
        message = EmailMessage()
        message["From"] = smtp.sender
        message["To"] = self.settings.ALERT_EMAIL
        message["Subject"] = MSG_ALERT_SUBJECT
        message.set_content(text)
        try:
            await aiosmtplib.send(
                message,
                hostname=smtp.host,
                port=smtp.port,
                username=smtp.username,
                password=smtp.password.get_secret_value() if smtp.password else None,
                start_tls=smtp.start_tls,
                timeout=ALERT_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            self.logger.warning("email_alert_error", error=str(exc))


async def alert(task_id: int | str, stage: str, error_message: str, severity: str, settings: Settings | None = None) -> None:
    """Send an alert using provided or default settings.

    Args:
        task_id: Failed task identifier.
        stage: Failed pipeline stage.
        error_message: Error details.
        severity: Severity level.
        settings: Optional application settings.

    Returns:
        None.
    """

    await AlertManager(settings or Settings()).alert(task_id, stage, error_message, severity)

