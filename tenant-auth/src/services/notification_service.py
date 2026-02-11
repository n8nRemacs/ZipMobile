import logging
from src.storage.supabase import get_supabase

logger = logging.getLogger("tenant-auth")


def get_preferences(user_id: str) -> list[dict]:
    """Get notification preferences for a user."""
    sb = get_supabase()
    resp = (
        sb.table("notification_preferences")
        .select("*")
        .eq("user_id", user_id)
        .order("channel")
        .execute()
    )
    return resp.data


def update_preferences(user_id: str, preferences: list[dict]) -> list[dict]:
    """
    Replace notification preferences for a user.
    Each item: {channel, event_type, is_enabled}
    """
    sb = get_supabase()

    # Delete existing preferences
    existing = sb.table("notification_preferences").select("id").eq("user_id", user_id).execute()
    for row in existing.data:
        sb.table("notification_preferences").delete().eq("id", row["id"]).execute()

    # Insert new
    results = []
    for pref in preferences:
        resp = sb.table("notification_preferences").insert({
            "user_id": user_id,
            "channel": pref["channel"],
            "event_type": pref["event_type"],
            "is_enabled": pref.get("is_enabled", True),
        }).execute()
        if resp.data:
            results.extend(resp.data)

    return results


def get_history(user_id: str, limit: int = 50) -> list[dict]:
    """Get notification history for a user."""
    sb = get_supabase()
    resp = (
        sb.table("notification_history")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data
