import logging
from src.providers.base import OtpProvider

logger = logging.getLogger("tenant-auth")


class SmsOtpProvider(OtpProvider):
    """SMS OTP provider (smsru/smsc). Stub — implement when ready."""

    @property
    def channel(self) -> str:
        return "sms"

    def send_otp(self, target: str, code: str, purpose: str) -> bool:
        logger.warning("SMS provider not configured, falling back to console log")
        logger.info("SMS OTP for %s: %s (purpose: %s)", target, code, purpose)
        return True
