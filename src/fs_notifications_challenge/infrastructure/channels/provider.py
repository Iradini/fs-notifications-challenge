import asyncio
import logging
import random
from typing import Any
from uuid import uuid4

logger = logging.getLogger("notifications.provider")


class ProviderUnavailableError(Exception):
    """Transient provider failure (timeout, 5xx, throlling). Senders turn this
    into DeliveryResult.transient(...) so the worker retries with backoff."""


class SimulatedProvider:
    """Stands in for SES / Twilio / FCM."""

    def __init__(self, name: str, failure_rate: float = 0.0, rng: random.Random | None = None) -> None:
        self.name = name
        self.failure_rate = failure_rate
        self._rng = rng or random.Random()


    async def transmit(self, payload: dict[str, Any]) -> str:
        await asyncio.sleep(0)  # A real provider call is network I/O
        if self.failure_rate and self._rng.random() < self.failure_rate:
            raise ProviderUnavailableError(f"{self.name} unavailable (simulated)")
        message_id = f"{self.name}-{uuid4().hex[:12]}"
        # Simulated sender: no real delivery, just say it happened
        token = str(payload.get("token", ""))
        to = payload.get("to") or f"device {token[:6]}..."  # never log a whole push token
        logger.info("Message sent | %s -> %s | id=%s", self.name.upper(), to, message_id)
        return message_id