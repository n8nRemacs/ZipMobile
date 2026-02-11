import hashlib
import hmac
import httpx
import json
import logging
import time
from urllib.parse import parse_qs, unquote

from src.config import settings
from src.storage.supabase import get_supabase
from src.services import jwt_service, user_service, billing_v2_service

logger = logging.getLogger("tenant-auth")


def get_phone_from_bot_updates(telegram_user_id: int) -> str | None:
    """
    Get phone number from Telegram Bot API getUpdates.
    After requestContact, Telegram sends the contact as a message to the bot.
    We fetch recent updates and look for a contact message from this user.
    """
    bot_token = settings.telegram_bot_token
    if not bot_token:
        return None

    try:
        resp = httpx.get(
            f"https://api.telegram.org/bot{bot_token}/getUpdates",
            params={"limit": 50},
            timeout=5.0,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning("getUpdates failed: %s", data)
            return None

        # Search from newest to oldest
        for update in reversed(data.get("result", [])):
            msg = update.get("message", {})
            contact = msg.get("contact")
            if contact and contact.get("user_id") == telegram_user_id:
                phone = contact.get("phone_number")
                logger.info("Found shared phone for user %s: %s", telegram_user_id, phone)
                return phone

        logger.info("No contact message found for user %s in %d updates",
                     telegram_user_id, len(data.get("result", [])))
        return None
    except Exception as e:
        logger.error("getUpdates error: %s", e)
        return None


def validate_init_data(init_data: str, bot_token: str) -> dict:
    """
    Validate Telegram WebApp initData signature.
    Returns parsed user dict on success, raises ValueError on failure.
    """
    parsed = parse_qs(init_data)

    if "hash" not in parsed:
        raise ValueError("Missing hash in initData")

    received_hash = parsed.pop("hash")[0]

    # Build data_check_string: sorted key=value pairs joined by \n
    data_check_string = "\n".join(
        f"{k}={v[0]}" for k, v in sorted(parsed.items())
    )

    # secret_key = HMAC-SHA256("WebAppData", bot_token)
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()

    # calculated_hash = HMAC-SHA256(secret_key, data_check_string)
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Invalid initData signature")

    # Check auth_date freshness (5 minutes)
    auth_date_str = parsed.get("auth_date", [None])[0]
    if auth_date_str:
        auth_date = int(auth_date_str)
        if time.time() - auth_date > 300:
            raise ValueError("initData expired (older than 5 minutes)")

    # Parse user JSON
    user_str = parsed.get("user", [None])[0]
    if not user_str:
        raise ValueError("No user data in initData")

    tg_user = json.loads(unquote(user_str))
    return tg_user


def find_existing_user(
    tg_user: dict,
    telegram_phone: str | None,
    phone: str | None = None,
) -> dict | None:
    """
    Check if user already exists by telegram_chat_id, telegram_phone, or phone.
    Returns {user, tenant} dict or None.
    """
    sb = get_supabase()

    # Check by telegram_chat_id
    resp = (
        sb.table("tenant_users")
        .select("*")
        .eq("telegram_chat_id", tg_user["id"])
        .limit(1)
        .execute()
    )
    user = resp.data[0] if resp.data else None

    # Check by telegram_phone if not found by chat_id
    if not user and telegram_phone:
        resp = (
            sb.table("tenant_users")
            .select("*")
            .eq("telegram_phone", telegram_phone)
            .limit(1)
            .execute()
        )
        user = resp.data[0] if resp.data else None

    # Check by phone if not found by telegram fields
    if not user and phone:
        resp = (
            sb.table("tenant_users")
            .select("*")
            .eq("phone", phone)
            .limit(1)
            .execute()
        )
        user = resp.data[0] if resp.data else None

    if not user:
        return None

    # Get tenant info
    tenant_resp = (
        sb.table("tenants")
        .select("company_name,city,address")
        .eq("id", user["tenant_id"])
        .limit(1)
        .execute()
    )
    tenant = tenant_resp.data[0] if tenant_resp.data else {}

    return {
        "user_id": user["id"],
        "tenant_id": user["tenant_id"],
        "name": user.get("name"),
        "phone": user.get("phone"),
        "company_name": tenant.get("company_name"),
        "city": tenant.get("city"),
        "address": tenant.get("address"),
        "available_channels": user.get("available_channels") or [],
        "preferred_channel": user.get("preferred_channel") or "telegram",
    }


def register_via_telegram(
    phone: str,
    name: str,
    company_name: str,
    city: str,
    address: str | None,
    available_channels: list[str],
    preferred_channel: str,
    tg_user: dict,
    telegram_phone: str | None = None,
) -> dict:
    """
    Register a new tenant via Telegram Mini App.
    Returns {"status": "created", ...tokens} or {"status": "existing", ...user_data}.
    """
    sb = get_supabase()

    # Check if user already exists by telegram_chat_id or telegram_phone
    existing = find_existing_user(tg_user, telegram_phone)
    if existing:
        return {"status": "existing", **existing}

    # Create tenant + user
    user = user_service.create_tenant_and_user(phone, None, name)

    # Update tenant with company info
    sb.table("tenants").update({
        "company_name": company_name,
        "city": city,
        "address": address,
    }).eq("id", user["tenant_id"]).execute()

    # Create free billing v2 subscriptions
    billing_v2_service.create_free_subscriptions(user["tenant_id"])

    # telegram_phone: if provided separately — use it; otherwise same as phone
    tg_phone_value = telegram_phone if telegram_phone else phone

    # phone_verified: true only if the main phone IS the telegram phone
    phone_is_tg = not telegram_phone or phone == telegram_phone
    phone_verified = phone_is_tg

    # Update user with telegram data
    sb.table("tenant_users").update({
        "telegram_chat_id": tg_user["id"],
        "telegram_username": tg_user.get("username"),
        "telegram_first_name": tg_user.get("first_name"),
        "telegram_last_name": tg_user.get("last_name"),
        "telegram_phone": tg_phone_value,
        "available_channels": available_channels,
        "preferred_channel": preferred_channel,
        "phone_verified": phone_verified,
    }).eq("id", user["id"]).execute()

    # Create JWT pair
    token_pair = jwt_service.create_token_pair(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
    )

    return {
        "status": "created",
        **token_pair,
        "user_id": user["id"],
        "tenant_id": user["tenant_id"],
        "is_new": True,
    }


def update_and_login_via_telegram(
    tg_user: dict,
    phone: str | None = None,
    telegram_phone: str | None = None,
    name: str | None = None,
    company_name: str | None = None,
    city: str | None = None,
    address: str | None = None,
    available_channels: list[str] | None = None,
    preferred_channel: str | None = None,
) -> dict:
    """
    Update existing user profile and return JWT pair.
    Finds user by telegram_chat_id.
    """
    sb = get_supabase()

    # Find user by telegram_chat_id
    resp = (
        sb.table("tenant_users")
        .select("*")
        .eq("telegram_chat_id", tg_user["id"])
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise ValueError("User not found")

    user = resp.data[0]

    if not user.get("is_active", True):
        raise ValueError("Account deactivated")

    # Update user fields
    user_update: dict = {}
    if name is not None:
        user_update["name"] = name
    if phone is not None:
        user_update["phone"] = phone
        # phone_verified: true only if phone == telegram_phone
        tg_ph = telegram_phone or user.get("telegram_phone")
        user_update["phone_verified"] = (phone == tg_ph)
    if telegram_phone is not None:
        user_update["telegram_phone"] = telegram_phone
    if available_channels is not None:
        user_update["available_channels"] = available_channels
    if preferred_channel is not None:
        user_update["preferred_channel"] = preferred_channel

    if user_update:
        sb.table("tenant_users").update(user_update).eq("id", user["id"]).execute()

    # Update tenant fields
    tenant_update: dict = {}
    if company_name is not None:
        tenant_update["company_name"] = company_name
    if city is not None:
        tenant_update["city"] = city
    if address is not None:
        tenant_update["address"] = address

    if tenant_update:
        sb.table("tenants").update(tenant_update).eq("id", user["tenant_id"]).execute()

    # Create JWT pair
    token_pair = jwt_service.create_token_pair(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
    )

    return {
        **token_pair,
        "user_id": user["id"],
        "tenant_id": user["tenant_id"],
        "is_new": False,
    }


def auto_login_via_telegram(tg_user: dict) -> dict | None:
    """
    Auto-login by telegram_chat_id.
    Returns token dict or None if user not found.
    """
    sb = get_supabase()

    resp = (
        sb.table("tenant_users")
        .select("*")
        .eq("telegram_chat_id", tg_user["id"])
        .limit(1)
        .execute()
    )

    if not resp.data:
        return None

    user = resp.data[0]

    if not user.get("is_active", True):
        raise ValueError("Account deactivated")

    token_pair = jwt_service.create_token_pair(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
    )

    return {
        **token_pair,
        "user_id": user["id"],
        "tenant_id": user["tenant_id"],
        "phone_verified": user.get("phone_verified", False),
        "is_new": False,
    }


def register_or_login_via_web(
    telegram_id: int,
    username: str | None = None,
    first_name: str = "User",
    last_name: str | None = None,
    photo_url: str | None = None,
) -> dict:
    """
    Register a new user or login existing one via Telegram Web Login / Dev Login.
    Returns dict with tokens and is_new_user flag.
    """
    sb = get_supabase()

    # Check if user exists by telegram_chat_id
    resp = (
        sb.table("tenant_users")
        .select("*")
        .eq("telegram_chat_id", telegram_id)
        .limit(1)
        .execute()
    )

    if resp.data:
        # Existing user — login
        user = resp.data[0]
        if not user.get("is_active", True):
            raise ValueError("Account deactivated")

        token_pair = jwt_service.create_token_pair(
            user_id=user["id"],
            tenant_id=user["tenant_id"],
            role=user["role"],
        )
        return {
            **token_pair,
            "is_new_user": False,
        }

    # New user — register
    display_name = first_name
    if last_name:
        display_name += f" {last_name}"

    user = user_service.create_tenant_and_user(
        phone=f"+0{telegram_id}",  # placeholder phone
        email=None,
        name=display_name,
    )

    # Update user with telegram data
    sb.table("tenant_users").update({
        "telegram_chat_id": telegram_id,
        "telegram_username": username,
        "telegram_first_name": first_name,
        "telegram_last_name": last_name,
        "phone_verified": False,
    }).eq("id", user["id"]).execute()

    # Create free billing v2 subscriptions
    billing_v2_service.create_free_subscriptions(user["tenant_id"])

    token_pair = jwt_service.create_token_pair(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
    )
    return {
        **token_pair,
        "is_new_user": True,
    }


def validate_login_widget(data: dict, bot_token: str) -> None:
    """
    Validate Telegram Login Widget hash.
    Different from Mini App initData: secret = SHA256(token), NOT HMAC.
    Raises ValueError on failure.
    """
    received_hash = data.get("hash")
    if not received_hash:
        raise ValueError("Missing hash")

    # Build data_check_string from all fields except hash
    check_data = {k: v for k, v in data.items() if k != "hash"}
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(check_data.items())
    )

    # For Login Widget: secret = SHA256(bot_token)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Invalid Login Widget signature")

    # Check auth_date freshness (5 minutes)
    auth_date = data.get("auth_date")
    if auth_date and time.time() - int(auth_date) > 300:
        raise ValueError("Login data expired (older than 5 minutes)")


def web_login_via_telegram(telegram_user_id: int) -> dict | None:
    """
    Login via Telegram Login Widget by telegram_chat_id.
    Returns token dict with phone_verified or None if user not found.
    """
    sb = get_supabase()

    resp = (
        sb.table("tenant_users")
        .select("*")
        .eq("telegram_chat_id", telegram_user_id)
        .limit(1)
        .execute()
    )

    if not resp.data:
        return None

    user = resp.data[0]

    if not user.get("is_active", True):
        raise ValueError("Account deactivated")

    token_pair = jwt_service.create_token_pair(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
    )

    return {
        **token_pair,
        "user_id": user["id"],
        "tenant_id": user["tenant_id"],
        "phone_verified": user.get("phone_verified", False),
        "is_new": False,
    }
