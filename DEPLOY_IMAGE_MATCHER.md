# Deploy Image-Matcher to myaleena.com

The image-matcher (Python + PyTorch + OpenCLIP) **cannot run on Cloudflare Workers**. Use this hybrid setup:

## Architecture

```
Zendesk → myaleena.com/webhook/zendesk (Cloudflare Worker)
              ↓ proxy (instant 200)
         [Python backend on Render/Railway/etc.]
```

## 1. Deploy Python Backend (Render)

1. **Push your repo** to GitHub (including `image-matcher/` and `render.yaml`).

2. **Open Render Blueprint:**
   ```
   https://dashboard.render.com/blueprint/new?repo=https://github.com/YOUR_USER/YOUR_REPO
   ```

3. **Connect the repo**, then **Apply** the Blueprint.

4. **Set environment variables** in Render Dashboard (Settings → Environment):
   - `ZENDESK_SUBDOMAIN`, `ZENDESK_EMAIL`, `ZENDESK_API_TOKEN`
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
   - `SHOPIFY_STOREFRONT_TOKEN` (or leave blank for sitemap fallback)
   - `ZENDESK_WEBHOOK_SECRET` (optional, for signature verification)

5. **Note your Render URL** (e.g. `https://image-matcher-xxxx.onrender.com`).

6. **Sync catalog** once after deploy: `POST https://your-render-url/sync/catalog` (if using Shopify token).

## 2. Configure Cloudflare Worker

1. **Add `IMAGE_MATCHER_URL`** to your Worker:
   - Dashboard: Workers & Pages → your worker → Settings → Variables
   - Add variable: `IMAGE_MATCHER_URL` = `https://your-render-url.onrender.com` (no trailing slash)

   Or via wrangler:
   ```bash
   npx wrangler secret put IMAGE_MATCHER_URL  # Enter your Render URL when prompted
   ```

2. **Ensure your Worker route** covers `myaleena.com/webhook/zendesk` (or whatever path Zendesk uses).

## 3. Zendesk Webhook URL

Point Zendesk to:
```
https://myaleena.com/webhook/zendesk
```

The Worker receives it, returns 200 immediately, and forwards to the Python backend in the background.

## Alternative Hosting (Railway, Fly.io)

- **Railway**: Create a new service from repo, set `Start Command` to `cd image-matcher && uvicorn main:app --host 0.0.0.0 --port $PORT`, add env vars.
- **Fly.io**: `fly launch` from repo root, use a Dockerfile or `fly.toml` with the correct build/start commands.

## Streamlit Labeling UI

The labeling app (`streamlit run labeling_app.py`) runs locally—it reads from Supabase and fetches images from Zendesk. No need to host it in the cloud.
