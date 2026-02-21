# Image-to-Product Matcher: Logic and Potential Issues

## End-to-End Flow

```
1. Customer adds comment with image to Zendesk ticket
       ↓
2. Zendesk "Ticket updated" trigger fires
       ↓
3. Zendesk POSTs webhook to https://myaleena.com/webhook/zendesk
       ↓
4. Cloudflare Worker receives request
       - Returns 200 immediately (so Zendesk doesn't timeout)
       - Forwards payload to Render in background (ctx.waitUntil)
       ↓
5. Render image-matcher receives POST /webhook/zendesk
       - Extracts ticket_id from payload
       - Returns 200 immediately
       - Starts process_ticket_attachments as background task
       ↓
6. Background task (process_ticket_attachments):
       a. Fetches ALL comments for ticket from Zendesk API
       b. Filters to image attachments only
       c. For each attachment:
          - Downloads image from Zendesk content_url
          - Loads matcher (if not loaded: reads catalog.json, builds FAISS index from product images)
          - Embeds ticket image with OpenCLIP
          - Searches FAISS for nearest product images
          - Aggregates to product-level, returns top-5
          - Logs to Supabase image_prediction_log
          - Optionally adds Zendesk internal note (if write-back enabled)
       d. Deletes downloaded image
```

## Potential Issues

### 1. **Background task may never run (most likely)**

On Render (and many PaaS), after the HTTP response is sent, the request is "done." FastAPI `BackgroundTasks` run in the same process **after** the response. If the platform recycles the worker or considers the request finished, the background task can be **killed before it completes**.

**Symptom:** Webhook returns 200, but nothing appears in `image_prediction_log`.

**Fix options:**
- Process **synchronously** (keep the request open until done) – may hit Render’s 30s timeout
- Use a **queue** (Redis, Supabase, etc.) – Worker enqueues, separate worker processes
- Use **Render Cron** or similar to poll for new tickets and process in a dedicated job

---

### 2. **Catalog lost on cold start**

Render’s filesystem is ephemeral. On deploy or cold start, `/tmp` (and thus `catalog.json`) is wiped.

**Symptom:** `matcher_loaded: false`, "No catalog loaded, skip matching".

**Fix:** Run `/sync/catalog` or `/sync/quick` after each cold start, or use persistent storage (e.g. Supabase, S3) for the catalog.

---

### 3. **First matcher load is very slow**

When `get_matcher()` runs for the first time, it:
- Reads `catalog.json`
- For **every** product image URL, fetches the image and embeds it
- Builds a FAISS index

For 500 products × 3 images = 1,500 HTTP requests + 1,500 embeddings. This can take **many minutes**. The background task may be killed before it finishes.

**Fix options:**
- Pre-build the index and persist it (e.g. as a file or in object storage)
- Use a smaller catalog for testing
- Run index build as a separate job (e.g. after sync) and load a prebuilt index

---

### 4. **Duplicate predictions**

Every "Ticket updated" webhook re-processes **all** attachments on the ticket. If a ticket is updated multiple times, the same attachments are processed again, creating duplicate rows in `image_prediction_log`.

**Fix:** Before inserting, check if a prediction for `(zendesk_attachment_id)` already exists, and skip or update instead.

---

### 5. **Zendesk webhook payload**

We expect `ticket_id` from:
- `body.detail.id`
- `body.ticket_id`
- `body.id`

Zendesk payloads vary by event. If "Ticket updated" uses a different structure, we might not get `ticket_id` and would return 400.

---

### 6. **Two webhooks required**

- `/webhook` → text classifier (ticket created)
- `/webhook/zendesk` → image matcher (ticket updated / comment added)

If only one webhook is configured in Zendesk, one of these flows will never run.

---

### 7. **Products with no images**

Catalog from sitemap may have products with `images: []`. Those are skipped when building the index. If most products have no images, the index can be nearly empty and matching will be poor.

---

## Recommended Next Steps

1. **Verify background task runs** – Add logging at the start of `process_ticket_attachments` and check Render logs when a webhook is received.
2. **Process synchronously for testing** – Temporarily run processing in the request handler (no `BackgroundTasks`) to confirm the rest of the flow works.
3. **Add deduplication** – Skip or update when a prediction for the same `zendesk_attachment_id` already exists.
4. **Persist catalog** – Store `catalog.json` (and ideally the FAISS index) in Supabase or similar so it survives restarts.
