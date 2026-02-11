import logging
from src.providers.base import OtpProvider

logger = logging.getLogger("tenant-auth")


class ConsoleOtpProvider(OtpProvider):
    """Dev/testing OTP provider that logs codes to stdout."""

    @property
    def channel(self) -> str:
        return "console"

    def send_otp(self, target: str, code: str, purpose: str) -> bool:
        logger.info(
            "═══════════════════════════════════════════\n"
            "  OTP CODE for %s\n"
            "  Target:  %s\n"
            "  Code:    %s\n"
            "  Purpose: %s\n"
            "═══════════════════════════════════════════",
            target, target, code, purpose,
        )
        return True
