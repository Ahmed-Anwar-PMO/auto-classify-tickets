"""
Image-to-Product-URL matcher: FastAPI service.
Receives Zendesk webhooks, downloads attachments, matches to shopaleena products, logs to Supabase.
"""

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks

from config import settings
from zendesk_client import (
    verify_webhook_signature,
    fetch_ticket_comments,
    iter_image_attachments,
    download_attachment,
    add_internal_note,
)
# Matcher imported lazily to avoid loading PyTorch at startup (OOM on free tier)
from preprocess import load_and_strip_exif
from supabase_client import get_client, log_image_prediction, upsert_ticket_image

# Lazy-loaded matcher (heavy)
_matcher: ProductMatcher | None = None
_data_dir = Path(settings.DATA_DIR)
_cache_dir = Path(settings.CACHE_DIR)


def get_matcher():
    """Lazy-load matcher (PyTorch/OpenCLIP) only when needed."""
    global _matcher
    if _matcher is not None:
        return _matcher
    from matcher import ProductMatcher, load_catalog_for_matcher
    catalog_path = _cache_dir / "catalog.json"
    catalog = load_catalog_for_matcher(
        catalog_path,
        settings.SHOPIFY_STORE_DOMAIN,
        settings.SHOPIFY_STOREFRONT_TOKEN,
    )
    if not catalog:
        return None
    _matcher = ProductMatcher(
        catalog,
        model_name=settings.EMBEDDING_MODEL,
        pretrained=settings.EMBEDDING_PRETRAINED,
        device="cpu",
    )
    return _matcher


async def process_ticket_attachments(ticket_id: int, correlation_id: str) -> None:
    """Background: fetch comments, download images, match, log."""
    if not settings.zendesk_ok:
        return
    comments = fetch_ticket_comments(
        settings.ZENDESK_SUBDOMAIN,
        settings.ZENDESK_EMAIL,
        settings.ZENDESK_API_TOKEN,
        ticket_id,
    )
    attachments = iter_image_attachments(comments)
    if not attachments:
        return

    matcher = get_matcher()
    if matcher is None:
        print(f"[{correlation_id}] No catalog loaded, skip matching")
        return

    supabase = get_client()
    download_dir = _data_dir / "downloads" / str(ticket_id)
    download_dir.mkdir(parents=True, exist_ok=True)

    for att in attachments:
        content_url = att.get("content_url")
        if not content_url:
            continue
        att_id = att.get("id")
        comment_id = att.get("comment_id")
        ext = ".jpg"
        dest = download_dir / f"{att_id}{ext}"

        path = download_attachment(
            content_url,
            settings.ZENDESK_EMAIL,
            settings.ZENDESK_API_TOKEN,
            dest,
        )
        if path is None:
            continue

        try:
            img, _ = load_and_strip_exif(path)
            top_k = matcher.match(path, top_k=5)
            pred = top_k[0] if top_k else None
            confidence = pred["score"] if pred else 0.0

            # Ensure JSON-serializable (no numpy types)
            top_k_clean = [
                {"product_id": p.get("product_id"), "url": p.get("url"), "score": float(p.get("score", 0))}
                for p in top_k
            ]
            log_row = {
                "zendesk_attachment_id": att_id,
                "zendesk_ticket_id": ticket_id,
                "predicted_product_id": pred.get("product_id") if pred else None,
                "predicted_product_url": pred.get("url") if pred else None,
                "top_k": top_k_clean,
                "confidence": float(confidence),
                "model_version": "openclip-vit-b32",
            }
            log_image_prediction(supabase, log_row)
            if settings.ZENDESK_WRITE_BACK_ENABLED and pred and float(confidence) >= settings.ZENDESK_WRITE_BACK_CONFIDENCE:
                note = f"[Auto] Matched product: {pred.get('url', '')}"
                add_internal_note(
                    settings.ZENDESK_SUBDOMAIN,
                    settings.ZENDESK_EMAIL,
                    settings.ZENDESK_API_TOKEN,
                    ticket_id,
                    note,
                )
            upsert_ticket_image(supabase, {
                "zendesk_ticket_id": ticket_id,
                "zendesk_comment_id": comment_id,
                "zendesk_attachment_id": att_id,
                "attachment_content_url": content_url,
            })
        finally:
            path.unlink(missing_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _data_dir.mkdir(parents=True, exist_ok=True)
    _cache_dir.mkdir(parents=True, exist_ok=True)
    yield
    # cleanup if needed


app = FastAPI(title="Image-to-Product Matcher", lifespan=lifespan)


@app.get("/")
@app.get("/ping")
def ping():
    """Minimal alive check. No dependencies."""
    return {"ok": True}


@app.get("/health")
def health():
    """Health check. Does NOT load matcher (avoids OOM on free tier)."""
    catalog_path = _cache_dir / "catalog.json"
    catalog_exists = catalog_path.exists()
    return {"ok": True, "catalog_cached": catalog_exists}


@app.post("/webhook/zendesk")
async def zendesk_webhook(request: Request, background_tasks: BackgroundTasks):
    """Zendesk webhook: validate signature, enqueue processing."""
    body_bytes = await request.body()
    timestamp = request.headers.get("x-zendesk-webhook-timestamp", "")
    signature = request.headers.get("x-zendesk-webhook-signature", "")

    if settings.ZENDESK_WEBHOOK_SECRET and not verify_webhook_signature(
        body_bytes, timestamp, signature, settings.ZENDESK_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    ticket_id = data.get("detail", {}).get("id") or data.get("ticket_id") or data.get("id")
    if not ticket_id:
        raise HTTPException(status_code=400, detail="Missing ticket ID")

    correlation_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(process_ticket_attachments, int(ticket_id), correlation_id)

    return {"ok": True, "ticket_id": ticket_id, "correlation_id": correlation_id}


@app.post("/sync/catalog")
def sync_catalog():
    """Fetch catalog from Shopify Storefront API or sitemap fallback."""
    domain = settings.SHOPIFY_STORE_DOMAIN or "shopaleena.com"
    out_path = _cache_dir / "catalog.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    for source, fetcher in [
        ("storefront", lambda: _fetch_storefront(domain)),
        ("sitemap", lambda: _fetch_sitemap(domain)),
    ]:
        try:
            catalog = fetcher()
            if catalog:
                from shopify_catalog import save_catalog_to_file
                save_catalog_to_file(catalog, out_path)
                global _matcher
                _matcher = None
                return {"ok": True, "products": len(catalog), "source": source}
        except Exception as e:
            if source == "sitemap":
                raise HTTPException(status_code=500, detail=str(e))
            continue
    raise HTTPException(status_code=500, detail="Could not fetch catalog from Storefront or sitemap")


def _fetch_storefront(domain: str) -> list:
    if not settings.SHOPIFY_STOREFRONT_TOKEN:
        return []
    from shopify_catalog import fetch_products_storefront
    return fetch_products_storefront(domain, settings.SHOPIFY_STOREFRONT_TOKEN)


def _fetch_sitemap(domain: str) -> list:
    from shopify_catalog import fetch_from_sitemap
    return fetch_from_sitemap(domain)


@app.post("/match")
async def match_image(request: Request):
    """Ad-hoc: match a single image (multipart). For testing."""
    matcher = get_matcher()
    if matcher is None:
        raise HTTPException(status_code=503, detail="Catalog not loaded")
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(status_code=400, detail="No file")
    dest = _cache_dir / f"match_{uuid.uuid4().hex}.tmp"
    try:
        content = await file.read()
        dest.write_bytes(content)
        top_k = matcher.match(dest, top_k=5)
        return {"top_k": top_k}
    finally:
        dest.unlink(missing_ok=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
