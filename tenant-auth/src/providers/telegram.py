import logging
from src.providers.base import OtpProvider

logger = logging.getLogger("tenant-auth")


class TelegramOtpProvider(OtpProvider):
    """Telegram Bot API OTP provider. Stub — implement when ready."""

    @property
    def channel(self) -> str:
        return "telegram"

    def send_otp(self, target: str, code: str, purpose: str) -> bool:
        logger.warning("Telegram provider not configured, falling back to console log")
        logger.info("Telegram OTP for %s: %s (purpose: %s)", target, code, purpose)
        return True
