# Image-to-Product-URL Matching Design

Design reference for the image-matcher system. See `image-matcher/` for implementation.

## Summary

- **Approach:** Retrieval-first with OpenCLIP embeddings + FAISS vector index
- **Catalog:** Shopify Storefront API (canonical URLs) or sitemap fallback
- **Ingestion:** Zendesk webhooks + Ticket Comments API for attachments
- **Targets:** Top-5 recall ≥85%, Top-1 accuracy 55–75%

## Architecture

- **Real-time:** Webhook → download attachment → embed → FAISS search → Supabase
- **Batch:** `scripts/backfill_zendesk.py` for historical tickets

## Config

Reuses `ZENDESK_*`, `SUPABASE_*` from worker. Add `SHOPIFY_STOREFRONT_TOKEN` for catalog.
