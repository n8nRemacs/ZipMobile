import logging
from src.providers.base import OtpProvider

logger = logging.getLogger("tenant-auth")


class WhatsAppOtpProvider(OtpProvider):
    """WhatsApp Business API OTP provider. Stub — implement when ready."""

    @property
    def channel(self) -> str:
        return "whatsapp"

    def send_otp(self, target: str, code: str, purpose: str) -> bool:
        logger.warning("WhatsApp provider not configured, falling back to console log")
        logger.info("WhatsApp OTP for %s: %s (purpose: %s)", target, code, purpose)
        return True
