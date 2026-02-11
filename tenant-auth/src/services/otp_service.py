import secrets
import logging
from datetime import datetime, timezone, timedelta

from src.config import settings
from src.storage.supabase import get_supabase
from src.providers.base import OtpProvider
from src.providers.console import ConsoleOtpProvider
from src.providers.sms import SmsOtpProvider
from src.providers.telegram import TelegramOtpProvider
from src.providers.whatsapp import WhatsAppOtpProvider
from src.providers.vk_max import VkMaxOtpProvider
from src.providers.email_provider import EmailOtpProvider

logger = logging.getLogger("tenant-auth")

_providers: dict[str, OtpProvider] = {
    "console": ConsoleOtpProvider(),
    "sms": SmsOtpProvider(),
    "telegram": TelegramOtpProvider(),
    "whatsapp": WhatsAppOtpProvider(),
    "vk_max": VkMaxOtpProvider(),
    "email": EmailOtpProvider(),
}


def _get_provider(channel: str) -> OtpProvider:
    if settings.otp_provider == "console":
        return _providers["console"]
    return _providers.get(channel, _providers["console"])


def generate_code() -> str:
    """Generate a random numeric OTP code."""
    return "".join(str(secrets.randbelow(10)) for _ in range(settings.otp_length))


def check_rate_limit(target: str) -> bool:
    """Check if target hasn't exceeded max OTP requests per hour."""
    sb = get_supabase()
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = (
        sb.table("verification_codes")
        .select("id")
        .eq("target", target)
        .gte("created_at", one_hour_ago)
        .execute()
    )
    return len(resp.data) < settings.otp_max_codes_per_hour


def send_otp(target: str, target_type: str, channel: str, purpose: str) -> dict:
    """Generate, store, and send OTP. Returns info dict or raises."""
    if not check_rate_limit(target):
        raise ValueError("Too many OTP requests. Try again later.")

    code = generate_code()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expire_minutes)).isoformat()

    sb = get_supabase()

    # Invalidate previous unused codes for same target+purpose
    old_codes = (
        sb.table("verification_codes")
        .select("id")
        .eq("target", target)
        .eq("purpose", purpose)
        .eq("is_used", False)
        .execute()
    )
    for row in old_codes.data:
        sb.table("verification_codes").update({"is_used": True}).eq("id", row["id"]).execute()

    # Determine actual channel to store
    actual_channel = channel if settings.otp_provider != "console" else "console"

    # Store new code
    sb.table("verification_codes").insert({
        "target": target,
        "target_type": target_type,
        "code": code,
        "channel": actual_channel,
        "purpose": purpose,
        "max_attempts": settings.otp_max_attempts,
        "expires_at": expires_at,
    }).execute()

    # Send via provider
    provider = _get_provider(channel)
    sent = provider.send_otp(target, code, purpose)
    if not sent:
        logger.error("Failed to send OTP to %s via %s", target, channel)
        raise ValueError("Failed to send OTP")

    return {
        "channel": actual_channel,
        "expires_in": settings.otp_expire_minutes * 60,
    }


def verify_otp(target: str, code: str, purpose: str) -> bool:
    """Verify OTP code. Returns True if valid, raises on failure."""
    sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    resp = (
        sb.table("verification_codes")
        .select("*")
        .eq("target", target)
        .eq("purpose", purpose)
        .eq("is_used", False)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not resp.data:
        raise ValueError("No pending verification code found")

    row = resp.data[0]

    # Check expiration
    expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        sb.table("verification_codes").update({"is_used": True}).eq("id", row["id"]).execute()
        raise ValueError("Verification code expired")

    # Check attempts
    if row["attempts"] >= row["max_attempts"]:
        sb.table("verification_codes").update({"is_used": True}).eq("id", row["id"]).execute()
        raise ValueError("Too many attempts. Request a new code.")

    # Increment attempts
    sb.table("verification_codes").update({"attempts": row["attempts"] + 1}).eq("id", row["id"]).execute()

    # Check code
    if row["code"] != code:
        remaining = row["max_attempts"] - row["attempts"] - 1
        raise ValueError(f"Invalid code. {remaining} attempts remaining.")

    # Mark as used
    sb.table("verification_codes").update({"is_used": True}).eq("id", row["id"]).execute()
    return True
