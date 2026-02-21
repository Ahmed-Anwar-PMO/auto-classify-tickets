/**
 * Log prediction to Supabase for audit and analytics.
 */

export async function logPrediction(env, row) {
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_KEY) return;
  const res = await fetch(`${env.SUPABASE_URL}/rest/v1/classification_log`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'apikey': env.SUPABASE_SERVICE_KEY,
      'Authorization': `Bearer ${env.SUPABASE_SERVICE_KEY}`,
      'Prefer': 'return=minimal'
    },
    body: JSON.stringify({
      ticket_id: row.ticket_id,
      label: row.label,
      score: row.score,
      action: row.action,
      model_version: row.model_version
    })
  });
  if (!res.ok) {
    console.warn('Supabase log failed:', res.status, await res.text());
  }
}
