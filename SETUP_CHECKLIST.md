# Setup Checklist (No Cost)

## Prerequisites
- [ ] Supabase account (free)
- [ ] Cloudflare account + domain (free)
- [ ] Zendesk Team Suite (yours)
- [ ] Google account (for Apps Script)

---

## 1. Supabase (≈5 min)
- [ ] Create project at supabase.com
- [ ] Run SQL: copy `supabase/migrations/001_initial.sql` → SQL Editor → Run
- [ ] Copy: Project URL, `service_role` key (Settings → API)

## 2. Cloudflare Worker (≈10 min)
- [ ] `cd worker && npm install`
- [ ] `npx wrangler login`
- [ ] `npx wrangler secret put ZENDESK_API_TOKEN`
- [ ] `npx wrangler secret put SUPABASE_SERVICE_KEY`
- [ ] Add vars (Dashboard or `wrangler.toml`):
  - `ZENDESK_SUBDOMAIN` (e.g. `mycompany`)
  - `ZENDESK_EMAIL`
  - `REASON_FIELD_ID` (from step 3)
  - `SUPABASE_URL`
- [ ] `npx wrangler deploy`
- [ ] Add route: `classify.yourdomain.com/webhook` → this Worker

## 3. Zendesk (≈10 min)
- [ ] Create "Reason for contact" drop-down field ([ZENDESK_SETUP.md](ZENDESK_SETUP.md))
- [ ] Note field ID (in field URL or API)
- [ ] Create API token
- [ ] Create webhook → URL = Worker URL
- [ ] Create trigger: Ticket created → Notify webhook

## 4. Image-to-Product Matcher (optional)
- [ ] `cd image-matcher && pip install -r requirements.txt`
- [ ] Copy `.env.example` → `.env`, reuse ZENDESK_*, SUPABASE_*; add SHOPIFY_STOREFRONT_TOKEN or leave blank (sitemap fallback)
- [ ] Run `supabase/migrations/002_image_product_matching.sql` in Supabase
- [ ] `python scripts/sync_catalog.py` to fetch catalog
- [ ] `python main.py` or `uvicorn main:app --port 8000`
- [ ] Add second Zendesk webhook + trigger (see ZENDESK_SETUP.md)

## 5. Google Apps Script (optional)
- [ ] New Sheet → Extensions → Apps Script
- [ ] Paste `apps-script/Code.gs`, fill in Zendesk + Sheet ID
- [ ] Run `setupSheet`, then `exportTicketsForLabeling`

---

## Test
1. Create a test ticket in Zendesk with body: "I was charged twice, please refund"
2. Check ticket: should have `reason__billing__duplicate_charge` tag and Reason field set
3. Check Supabase `classification_log` table for audit row
