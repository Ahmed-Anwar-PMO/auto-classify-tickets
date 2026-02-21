# Tech Stack: Auto-Classify Zendesk Tickets (100% Free)

## Your Existing Assets

| Asset | Purpose |
|-------|---------|
| **Supabase** | Audit logs, taxonomy storage, prediction history |
| **Cloudflare domain** | Host the classification webhook endpoint |
| **Zendesk Team Suite** | Source of tickets, triggers, webhooks, custom fields |
| **Google Apps Script** | Bulk export helper, labeling spreadsheet, backup receiver |

## Complete Stack (All Free Tiers)

| Layer | Technology | Free Tier | Role |
|-------|------------|-----------|------|
| **Webhook receiver** | Cloudflare Workers | 100k req/day, 10ms CPU/req | Receives Zendesk webhook, runs classifier, updates ticket |
| **Classification** | Rule-based (keyword/regex) | N/A | Runs in Worker; no external API cost |
| **Database** | Supabase (PostgreSQL) | 500MB DB, 2 projects | Audit log, taxonomy, prediction history |
| **Hosting / domain** | Cloudflare | Free | Worker at `classify.yourdomain.com` |
| **Ticketing** | Zendesk Team Suite | Your plan | Triggers, webhooks, custom fields, API |
| **Bulk / backup** | Google Apps Script | Free quotas | Export tickets for labeling, fallback webhook |

## Why This Fits the 10ms CPU Limit

- **CPU time** = only your code executing; **network waits** (fetch to Zendesk, Supabase) do **not** count.
- Rule-based classification (keyword matching, regex) typically uses **&lt; 1ms** CPU.
- If you later add ML, move inference to Supabase Edge Functions (higher limits) or an external free-tier API.

## Architecture Diagram

```
Zendesk (ticket created)
    → Trigger fires
    → Webhook POST → https://classify.yourdomain.com/webhook
    → Cloudflare Worker:
        1. Parse webhook payload
        2. Fetch ticket + first comment from Zendesk API
        3. Run rule-based classifier
        4. Update ticket (custom field + tags) via Zendesk API
        5. Log to Supabase (async, non-blocking)
    → Done
```

## Optional: Future Upgrades (Still Free)

| Upgrade | Option | Notes |
|---------|--------|-------|
| Better model | Hugging Face Inference API | Free tier rate-limited |
| More CPU | Supabase Edge Functions | 500k invocations/month free |
| Fallback webhook | Google Apps Script Web App | 6-min execution limit, good for low volume |
