from abc import ABC, abstractmethod


class OtpProvider(ABC):
    """Abstract base class for OTP delivery providers."""

    @abstractmethod
    def send_otp(self, target: str, code: str, purpose: str) -> bool:
        """Send OTP code to target. Returns True on success."""
        ...

    @property
    @abstractmethod
    def channel(self) -> str:
        """Provider channel name (sms, telegram, etc.)."""
        ...
