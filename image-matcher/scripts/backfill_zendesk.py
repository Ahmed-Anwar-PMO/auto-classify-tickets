#!/usr/bin/env python3
"""Backfill: fetch ticket events with comment_events, download attachments, run matching."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from zendesk_client import fetch_ticket_comments, iter_image_attachments, download_attachment
from matcher import ProductMatcher, load_catalog_for_matcher
from preprocess import load_and_strip_exif
from supabase_client import get_client, log_image_prediction


def main():
    if not settings.zendesk_ok:
        print("Zendesk not configured. Set ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN.")
        return
    ticket_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not ticket_id:
        print("Usage: python backfill_zendesk.py <ticket_id>")
        return

    ticket_id = int(ticket_id)
    catalog_path = Path(settings.CACHE_DIR) / "catalog.json"
    catalog = load_catalog_for_matcher(catalog_path, settings.SHOPIFY_STORE_DOMAIN, settings.SHOPIFY_STOREFRONT_TOKEN)
    if not catalog:
        print("No catalog. Run: python scripts/sync_catalog.py")
        return

    matcher = ProductMatcher(catalog, device="cpu")
    comments = fetch_ticket_comments(settings.ZENDESK_SUBDOMAIN, settings.ZENDESK_EMAIL, settings.ZENDESK_API_TOKEN, ticket_id)
    attachments = iter_image_attachments(comments)
    print(f"Ticket {ticket_id}: {len(attachments)} image attachments")

    supabase = get_client()
    download_dir = Path(settings.DATA_DIR) / "downloads" / str(ticket_id)
    download_dir.mkdir(parents=True, exist_ok=True)

    for att in attachments:
        content_url = att.get("content_url")
        if not content_url:
            continue
        att_id = att.get("id")
        dest = download_dir / f"{att_id}.jpg"
        path = download_attachment(content_url, settings.ZENDESK_EMAIL, settings.ZENDESK_API_TOKEN, dest)
        if path is None:
            print(f"  Attachment {att_id}: download failed")
            continue
        top_k = matcher.match(path, top_k=5)
        pred = top_k[0] if top_k else None
        top_k_clean = [{"product_id": p.get("product_id"), "url": p.get("url"), "score": float(p.get("score", 0))} for p in top_k]
        log_image_prediction(supabase, {
            "zendesk_attachment_id": att_id,
            "zendesk_ticket_id": ticket_id,
            "predicted_product_id": pred.get("product_id") if pred else None,
            "predicted_product_url": pred.get("url") if pred else None,
            "top_k": top_k_clean,
            "confidence": float(pred["score"]) if pred else 0.0,
            "model_version": "openclip-vit-b32",
        })
        print(f"  Attachment {att_id}: top1={pred.get('url', 'N/A')[:60] if pred else 'N/A'}...")


if __name__ == "__main__":
    main()
