/**
 * Zendesk Ticket Classification Worker
 * Receives webhook, classifies by reason, updates ticket. 100% free stack.
 */

import { classify } from './classifier.js';
import { fetchTicket, updateTicket } from './zendesk.js';
import { logPrediction } from './supabase.js';

const T_ASSIGN = 0.85;   // Auto-write reason
const T_SUGGEST = 0.60;  // Suggest only (future: agent app)

export default {
  async fetch(request, env, ctx) {
    if (request.method === 'OPTIONS') return corsResponse();
    if (request.method !== 'POST') return json(405, { error: 'Method not allowed' });

    const url = new URL(request.url);
    // Image matcher: proxy to Python backend (hosted elsewhere)
    if (url.pathname === '/webhook/zendesk' && env.IMAGE_MATCHER_URL) {
      return proxyToImageMatcher(request, env, ctx);
    }
    if (url.pathname !== '/webhook' && url.pathname !== '/') {
      return json(404, { error: 'Not found' });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return json(400, { error: 'Invalid JSON' });
    }

    // Zendesk webhook: body has event + detail (ticket.created, ticket.updated, etc.)
    const ticketId = body?.detail?.id ?? body?.ticket_id ?? body?.id;
    if (!ticketId) return json(400, { error: 'Missing ticket ID' });

    const subdomain = env.ZENDESK_SUBDOMAIN;
    const reasonFieldId = env.REASON_FIELD_ID ? parseInt(env.REASON_FIELD_ID, 10) : null;

    if (!subdomain || !env.ZENDESK_EMAIL || !env.ZENDESK_API_TOKEN) {
      return json(500, { error: 'Zendesk credentials not configured' });
    }

    try {
      const ticket = await fetchTicket(subdomain, env.ZENDESK_EMAIL, env.ZENDESK_API_TOKEN, ticketId);
      if (!ticket) return json(404, { error: 'Ticket not found' });

      const subject = ticket.subject || '';
      const firstBody = getFirstPublicComment(ticket, body);
      const text = [subject, firstBody].filter(Boolean).join('\n').trim() || 'No content';
      const tags = ticket.tags || [];
      const channel = ticket.via?.channel || 'unknown';
      const customFields = (ticket.custom_fields || []).reduce((acc, cf) => {
        acc[cf.id] = cf.value; return acc;
      }, {});

      const pred = classify({ subject, text, tags, channel, customFields });

      const action = pred.score >= T_ASSIGN ? 'auto_assign'
        : pred.score >= T_SUGGEST ? 'suggest'
        : 'abstain';

      const existingTags = ticket.tags || [];
      const reasonTag = `reason__${pred.label}`;
      const newTags = existingTags.includes(reasonTag)
        ? existingTags
        : [...existingTags, reasonTag];

      const updates = { tags: newTags };
      if (reasonFieldId && action === 'auto_assign') {
        const otherFields = (ticket.custom_fields || []).filter(cf => cf.id !== reasonFieldId);
        updates.custom_fields = [...otherFields, { id: reasonFieldId, value: pred.label }];
      }

      await updateTicket(subdomain, env.ZENDESK_EMAIL, env.ZENDESK_API_TOKEN, ticketId, {
        ...updates,
        safe_update: true,
        updated_stamp: ticket.updated_at
      });

      if (env.SUPABASE_URL && env.SUPABASE_SERVICE_KEY) {
        ctx.waitUntil(logPrediction(env, {
          ticket_id: ticketId,
          label: pred.label,
          score: pred.score,
          action,
          model_version: 'rules-v1'
        }));
      }

      return json(200, { ok: true, ticket_id: ticketId, label: pred.label, score: pred.score, action });
    } catch (e) {
      console.error(e);
      return json(500, { error: e.message || 'Classification failed' });
    }
  }
};

function getFirstPublicComment(ticket, webhookBody) {
  if (webhookBody?.detail?.description) return webhookBody.detail.description;
  if (ticket.description) return ticket.description;
  return '';
}

function json(status, data) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders() }
  });
}

function corsResponse() {
  return new Response(null, { status: 204, headers: corsHeaders() });
}

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
  };
}

/** Proxy Zendesk webhook to image-matcher Python backend. Returns 200 fast; forwards in background. */
async function proxyToImageMatcher(request, env, ctx) {
  const body = await request.clone().text();
  const ticketId = (() => {
    try {
      const d = JSON.parse(body);
      return d?.detail?.id ?? d?.ticket_id ?? d?.id;
    } catch { return null; }
  })();

  // Return 200 immediately so Zendesk doesn't timeout; forward in background
  ctx.waitUntil(
    fetch(`${env.IMAGE_MATCHER_URL.replace(/\/$/, '')}/webhook/zendesk`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-zendesk-webhook-signature-timestamp': request.headers.get('x-zendesk-webhook-signature-timestamp') || request.headers.get('x-zendesk-webhook-timestamp') || '',
        'x-zendesk-webhook-signature': request.headers.get('x-zendesk-webhook-signature') || '',
      },
      body,
    }).catch((e) => console.error('Image matcher forward failed:', e))
  );

  return json(200, { ok: true, ticket_id: ticketId, forwarded: true });
}
