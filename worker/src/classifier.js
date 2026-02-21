/**
 * Rule-based reason classifier. No external API, runs in Worker.
 * Add keywords per label; first match wins. Fallback: other_unclear.
 */

const TAXONOMY = [
  { label: 'billing__duplicate_charge', keywords: ['double charged', 'charged twice', 'duplicate charge', 'billed twice', 'double billing'] },
  { label: 'billing__refund_request', keywords: ['refund', 'money back', 'reimbursement', 'chargeback'] },
  { label: 'billing__payment_issue', keywords: ['payment failed', 'card declined', 'payment problem', 'billing error', 'invoice', 'subscription charge'] },
  { label: 'account__access', keywords: ['login', 'password', 'forgot password', 'reset password', 'cannot access', 'locked out', 'account lock'] },
  { label: 'account__cancel', keywords: ['cancel subscription', 'unsubscribe', 'cancel my account', 'close account'] },
  { label: 'shipping__delivery', keywords: ['shipping', 'delivery', 'tracking', 'where is my order', 'package', 'not arrived'] },
  { label: 'returns__exchange', keywords: ['return', 'exchange', 'send back', 'refund item'] },
  { label: 'product__defect', keywords: ['broken', 'defective', 'doesn\'t work', 'doa', 'dead on arrival', 'faulty'] },
  { label: 'product__howto', keywords: ['how to', 'how do i', 'how can i', 'where do i', 'where can i find'] },
  { label: 'technical__troubleshooting', keywords: ['error', 'bug', 'not working', 'issue', 'problem', 'fix', 'help with'] },
  { label: 'compliance__privacy', keywords: ['gdpr', 'delete my data', 'data deletion', 'privacy', 'personal information', 'dsar'] },
  { label: 'feedback__praise', keywords: ['thank you', 'great service', 'awesome', 'love your'] },
  { label: 'feedback__complaint', keywords: ['complaint', 'terrible', 'worst', 'frustrated', 'angry', 'unacceptable'] },
  { label: 'status__followup', keywords: ['any update', 'status', 'follow up', 'following up', 'when will', 'any news'] }
];

const FALLBACK = 'other_unclear';

export function classify({ subject = '', text = '', tags = [], channel, customFields }) {
  const combined = `${(subject + ' ' + text).toLowerCase()}`;
  const tagStr = tags.join(' ').toLowerCase();

  for (const { label, keywords } of TAXONOMY) {
    for (const kw of keywords) {
      if (combined.includes(kw) || tagStr.includes(kw.replace(/\s/g, '_'))) {
        return { label, score: 0.9, top_k: [{ label, score: 0.9 }] };
      }
    }
  }

  // Check for very short / empty
  if (combined.trim().length < 3) {
    return { label: FALLBACK, score: 0.5, top_k: [{ label: FALLBACK, score: 0.5 }] };
  }

  // Fuzzy: try partial keyword matches for medium confidence
  const words = combined.split(/\s+/).filter(Boolean);
  for (const { label, keywords } of TAXONOMY) {
    for (const kw of keywords) {
      const kwParts = kw.toLowerCase().split(/\s+/);
      const matches = kwParts.filter(p => words.some(w => w.includes(p) || p.includes(w)));
      if (matches.length >= Math.min(2, kwParts.length)) {
        return { label, score: 0.72, top_k: [{ label, score: 0.72 }] };
      }
    }
  }

  return { label: FALLBACK, score: 0.55, top_k: [{ label: FALLBACK, score: 0.55 }] };
}
