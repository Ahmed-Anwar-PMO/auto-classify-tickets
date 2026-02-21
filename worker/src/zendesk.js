/**
 * Zendesk API helpers. Uses basic auth with API token.
 */

const baseUrl = (subdomain) => `https://${subdomain}.zendesk.com/api/v2`;

export async function fetchTicket(subdomain, email, token, ticketId) {
  const auth = btoa(`${email}/token:${token}`);
  const res = await fetch(`${baseUrl(subdomain)}/tickets/${ticketId}.json`, {
    headers: { Authorization: `Basic ${auth}`, 'Content-Type': 'application/json' }
  });
  if (!res.ok) {
    if (res.status === 404) return null;
    throw new Error(`Zendesk fetch failed: ${res.status} ${await res.text()}`);
  }
  const data = await res.json();
  return data.ticket;
}

export async function updateTicket(subdomain, email, token, ticketId, payload) {
  const auth = btoa(`${email}/token:${token}`);
  const body = { ticket: payload };
  const res = await fetch(`${baseUrl(subdomain)}/tickets/${ticketId}.json`, {
    method: 'PUT',
    headers: { Authorization: `Basic ${auth}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const text = await res.text();
    if (res.status === 409) throw new Error('Ticket updated by another process (409). Retry with fresh data.');
    throw new Error(`Zendesk update failed: ${res.status} ${text}`);
  }
  return res.json();
}
