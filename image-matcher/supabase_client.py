"""Supabase client for image matching tables."""

from datetime import datetime, timezone

from supabase import create_client

from config import settings


def get_client():
    if not settings.supabase_ok:
        return None
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def log_image_prediction(client, row: dict) -> None:
    """Insert into image_prediction_log."""
    if client is None:
        return
    try:
        client.table("image_prediction_log").insert({
            "zendesk_attachment_id": row["zendesk_attachment_id"],
            "zendesk_ticket_id": row["zendesk_ticket_id"],
            "predicted_product_id": row.get("predicted_product_id"),
            "predicted_product_url": row.get("predicted_product_url"),
            "top_k": row.get("top_k", []),
            "confidence": row.get("confidence"),
            "model_version": row.get("model_version", "openclip-vit-b32"),
        }).execute()
    except Exception as e:
        print(f"Supabase log failed: {e}")


def upsert_ticket_image(client, row: dict) -> None:
    """Upsert ticket_image (for labeling workflow)."""
    if client is None:
        return
    try:
        client.table("ticket_image").upsert({
            "zendesk_ticket_id": row["zendesk_ticket_id"],
            "zendesk_comment_id": row["zendesk_comment_id"],
            "zendesk_attachment_id": row["zendesk_attachment_id"],
            "attachment_content_url": row["attachment_content_url"],
        }, on_conflict="zendesk_attachment_id").execute()
    except Exception as e:
        print(f"Supabase ticket_image upsert failed: {e}")


def update_prediction_review(client, log_id: int, accepted: bool, overridden_product_id: str | None = None, overridden_product_url: str | None = None) -> None:
    """Update image_prediction_log after reviewer feedback."""
    if client is None:
        return
    try:
        data: dict = {"accepted": accepted}
        if overridden_product_id is not None:
            data["overridden_product_id"] = overridden_product_id
        if overridden_product_url is not None:
            data["predicted_product_url"] = overridden_product_url
        client.table("image_prediction_log").update(data).eq("id", log_id).execute()
    except Exception as e:
        print(f"Supabase review update failed: {e}")


def update_ticket_image_ground_truth(client, zendesk_attachment_id: int, product_id: str, product_url: str, label_source: str = "manual") -> None:
    """Update ticket_image with ground truth from labeling."""
    if client is None:
        return
    try:
        client.table("ticket_image").update({
            "ground_truth_product_id": product_id,
            "ground_truth_product_url": product_url,
            "label_source": label_source,
            "labeled_at": datetime.now(timezone.utc).isoformat(),
        }).eq("zendesk_attachment_id", zendesk_attachment_id).execute()
    except Exception as e:
        print(f"Supabase ground truth update failed: {e}")


def fetch_unreviewed_predictions(client, limit: int = 50) -> list[dict]:
    """Fetch predictions where accepted is null."""
    if client is None:
        return []
    try:
        r = client.table("image_prediction_log").select("*").is_("accepted", "null").order("created_at", desc=True).limit(limit).execute()
        return r.data or []
    except Exception as e:
        print(f"Supabase fetch unreviewed failed: {e}")
        return []
