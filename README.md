# Auto-Classify Zendesk Tickets

Automated reason-for-contact classification using a **100% free** tech stack: Cloudflare Workers, Supabase, Zendesk, and Google Apps Script.

## Architecture

**Text classification (Worker):**
```
Zendesk (ticket created) → Trigger → Webhook → Cloudflare Worker
    → Fetch ticket → Rule-based classify → Update custom field + tags
    → Log to Supabase
```

**Image-to-product matching (Python service):**
```
Zendesk (ticket updated / comment) → Webhook → image-matcher (FastAPI)
    → Fetch comments/attachments → OpenCLIP embed → FAISS search
    → Log to Supabase image_prediction_log
```
See [image-matcher/README.md](image-matcher/README.md).

## Quick Start

### 1. Deploy Cloudflare Worker

```bash
cd worker
npm install
```

Set secrets and vars:

```bash
npx wrangler secret put ZENDESK_API_TOKEN    # Paste your Zendesk API token
npx wrangler secret put SUPABASE_SERVICE_KEY # Supabase service_role key (for logging)
```

Add to `wrangler.toml` under `[vars]` or via Dashboard:

- `ZENDESK_SUBDOMAIN` = your Zendesk subdomain (e.g. `mycompany`)
- `ZENDESK_EMAIL` = admin email used with API token
- `REASON_FIELD_ID` = Zendesk custom field ID for "Reason for contact"
- `SUPABASE_URL` = `https://xxxxx.supabase.co`
- `SUPABASE_SERVICE_KEY` = service_role key (not anon)

Deploy:

```bash
npx wrangler deploy
```

### 2. Configure Cloudflare Route

In Cloudflare Dashboard → Workers & Pages → your worker → Settings → Triggers:

- Add route: `classify.yourdomain.com/*` (or use workers.dev subdomain)

### 3. Set Up Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Run the migration: **SQL Editor** → paste contents of `supabase/migrations/001_initial.sql` → Run
3. Copy Project URL and service_role key from Settings → API

### 4. Configure Zendesk

Follow [ZENDESK_SETUP.md](ZENDESK_SETUP.md) to create the custom field, webhook, and trigger.

### 5. (Optional) Google Apps Script for Bulk Export

1. Create a new Google Sheet
2. Extensions → Apps Script
3. Paste `apps-script/Code.gs`, update `ZENDESK_*` and `SPREADSHEET_ID`
4. Run `setupSheet` once, then `exportTicketsForLabeling` to pull tickets for labeling

## Taxonomy (Customize in `worker/src/classifier.js`)

| Label | Display |
|-------|---------|
| billing__duplicate_charge | Billing: Duplicate charge |
| billing__refund_request | Billing: Refund request |
| account__access | Account: Access |
| shipping__delivery | Shipping & delivery |
| ... | See classifier.js for full list |

## Thresholds

- **T_assign (0.85)**: Auto-write reason and tag
- **T_suggest (0.60)**: Tag only, no custom field (future: agent sidebar)
- **Below**: Abstain, tag `reason__other_unclear`

## Files

| Path | Purpose |
|------|---------|
| `worker/` | Cloudflare Worker (text classification webhook) |
| `image-matcher/` | Python FastAPI service (image → product URL matching) |
| `supabase/migrations/` | DB schema (classification + image/product tables) |
| `apps-script/` | Google Apps Script for ticket export |
| `ZENDESK_SETUP.md` | Zendesk configuration steps |
| `TECH_STACK.md` | Tech stack overview |
