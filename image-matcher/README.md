# Image-to-Product-URL Matcher

Maps Zendesk ticket attachment images to exact product page URLs on shopaleena.com. Uses OpenCLIP embeddings + FAISS (design doc: minimal-cost retrieval-first).

## Prerequisites

- Python 3.11+
- Same Supabase + Zendesk credentials as the main worker
- (Optional) Shopify Storefront API token for catalog; otherwise uses sitemap

## Quick Start

```bash
cd image-matcher
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt

# Copy env (reuse worker vars)
copy .env.example .env
# Edit .env: ZENDESK_*, SUPABASE_*, SHOPIFY_* (or leave blank for sitemap)

# Sync catalog (Storefront API or sitemap)
python scripts/sync_catalog.py

# Run API
python main.py
# or: uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints

| Path | Method | Purpose |
|------|--------|---------|
| `/health` | GET | Health + matcher loaded |
| `/webhook/zendesk` | POST | Zendesk webhook receiver |
| `/sync/catalog` | POST | Re-fetch catalog from Shopify |
| `/match` | POST | Ad-hoc match (multipart file) |

## Zendesk Setup

See [ZENDESK_SETUP.md](../ZENDESK_SETUP.md) section "Image-to-Product Matcher" for webhook + trigger.

## Assisted Labeling

```bash
streamlit run labeling_app.py
```

Review unreviewed predictions, accept/override product match, store ground truth for evaluation.

## Backfill

```bash
python scripts/backfill_zendesk.py <ticket_id>
```

## Zendesk Write-Back (optional)

Set `ZENDESK_WRITE_BACK_ENABLED=true` and `ZENDESK_WRITE_BACK_CONFIDENCE=0.75` to add an internal note with the matched product URL when confidence exceeds the threshold.

## Supabase Migration

Run `supabase/migrations/002_image_product_matching.sql` in Supabase SQL Editor before using.
