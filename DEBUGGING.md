# Image-Matcher: Nothing Came Through – Debugging Guide

## 0. Worker Returns "Not found" (404)

If `https://myaleena.com/webhook/zendesk` returns `{"ok": false, "error": "Not found"}`:

1. **Routes:** Cloudflare Dashboard → Workers & Pages → zendesk-ticket-classifier → Domains & Routes. Ensure both exist:
   - `myaleena.com/*` (apex)
   - `*.myaleena.com/*` (subdomains)
   - To add apex via API: `worker/scripts/add-apex-route.ps1`

2. **IMAGE_MATCHER_URL:** Settings → Variables and Secrets. Must have `IMAGE_MATCHER_URL` = `https://image-matcher-whm0.onrender.com` (Production).

## 1. Verify Zendesk Webhook URL

The image webhook must use the **exact path** `/webhook/zendesk`:

- **Correct:** `https://myaleena.com/webhook/zendesk`
- **Wrong:** `https://myaleena.com/webhook` (that goes to text classifier, not image matcher)

**Check:** Zendesk Admin → Apps and integrations → Webhooks → your image webhook → Endpoint URL.

## 2. Verify Zendesk Trigger

The trigger must fire when a **comment with an image** is added:

- **Condition:** Ticket → Updated (or "Comment added" if your plan has it)
- **Action:** Notify webhook → select your image webhook

"Ticket created" only fires once; adding a reply with an image is a ticket **update**.

## 3. Wake Up Render (Free Tier)

Render free tier sleeps after ~15 min. A cold start can take 50+ seconds; the Worker may timeout before Render responds.

**Before testing:** Open in browser to wake the service:
```
https://YOUR-RENDER-URL.onrender.com/health
```
Wait until you see `{"ok": true}` (may take 30–60 sec on first load). Then create your ticket with image.

## 4. Sync Catalog (Required)

If the catalog was never synced, the matcher skips processing.

**Run:**
```powershell
curl -X POST https://YOUR-RENDER-URL.onrender.com/sync/catalog
```

**Check:** `https://YOUR-RENDER-URL.onrender.com/health` should show `"matcher_loaded": true` after sync.

## 5. Check Render Logs

Render Dashboard → your service → **Logs**

Look for:
- Incoming `POST /webhook/zendesk` requests
- `[correlation_id] No catalog loaded, skip matching` → run sync/catalog
- Python tracebacks → indicates an error

## 6. Check Zendesk Webhook Deliveries

Zendesk Admin → Apps and integrations → Webhooks → your webhook → **Delivery log**

- Status 200 = Worker received it
- Status 4xx/5xx or timeout = problem before Render

## 7. Manual Test (Bypass Zendesk)

**If you get "connection was closed"** – force TLS 1.2 first:
```powershell
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
```

Test via Worker (recommended):
```powershell
$json = '{"ticket_id": 303847}'
Invoke-RestMethod -Uri "https://myaleena.com/webhook/zendesk" -Method POST -ContentType "application/json" -Headers @{"x-webhook-secret"="22081994"} -Body $json
```

Or use the script (handles TLS automatically):
```powershell
.\worker\scripts\test-webhook.ps1 -TicketId 303847
```

Expected: `{"ok": true, "ticket_id": 303847, "forwarded": true}`

Or test Render directly:

```powershell
$json = '{"ticket_id": 303847}'
Invoke-RestMethod -Uri "https://image-matcher-whm0.onrender.com/webhook/zendesk" -Method POST -ContentType "application/json" -Headers @{"x-webhook-secret"="22081994"} -Body $json
```

Then check Supabase `image_prediction_log` table.
