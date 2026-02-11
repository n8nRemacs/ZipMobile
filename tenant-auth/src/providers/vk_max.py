import logging
from src.providers.base import OtpProvider

logger = logging.getLogger("tenant-auth")


class VkMaxOtpProvider(OtpProvider):
    """VK MAX Bot API OTP provider. Stub — implement when ready."""

    @property
    def channel(self) -> str:
        return "vk_max"

    def send_otp(self, target: str, code: str, purpose: str) -> bool:
        logger.warning("VK MAX provider not configured, falling back to console log")
        logger.info("VK MAX OTP for %s: %s (purpose: %s)", target, code, purpose)
        return True
