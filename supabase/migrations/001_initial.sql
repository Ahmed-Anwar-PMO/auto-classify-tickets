-- Classification audit log (predictions written back to Zendesk)
CREATE TABLE IF NOT EXISTS classification_log (
  id BIGSERIAL PRIMARY KEY,
  ticket_id BIGINT NOT NULL,
  label TEXT NOT NULL,
  score NUMERIC(5,4) NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('auto_assign', 'suggest', 'abstain')),
  model_version TEXT NOT NULL DEFAULT 'rules-v1',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_classification_log_ticket ON classification_log(ticket_id);
CREATE INDEX IF NOT EXISTS idx_classification_log_created ON classification_log(created_at);
CREATE INDEX IF NOT EXISTS idx_classification_log_action ON classification_log(action);

-- Taxonomy / label definitions (editable via dashboard)
CREATE TABLE IF NOT EXISTS taxonomy (
  id SERIAL PRIMARY KEY,
  label TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  keywords TEXT[] NOT NULL DEFAULT '{}',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO taxonomy (label, display_name, keywords, sort_order) VALUES
  ('billing__duplicate_charge', 'Billing: Duplicate charge', ARRAY['double charged', 'charged twice', 'duplicate charge', 'billed twice'], 1),
  ('billing__refund_request', 'Billing: Refund request', ARRAY['refund', 'money back', 'reimbursement', 'chargeback'], 2),
  ('billing__payment_issue', 'Billing: Payment issue', ARRAY['payment failed', 'card declined', 'invoice', 'subscription charge'], 3),
  ('account__access', 'Account: Access', ARRAY['login', 'password', 'forgot password', 'reset password', 'locked out'], 4),
  ('account__cancel', 'Account: Cancellation', ARRAY['cancel subscription', 'unsubscribe', 'cancel my account', 'close account'], 5),
  ('shipping__delivery', 'Shipping & delivery', ARRAY['shipping', 'delivery', 'tracking', 'where is my order', 'package'], 6),
  ('returns__exchange', 'Returns & exchange', ARRAY['return', 'exchange', 'send back'], 7),
  ('product__defect', 'Product defect', ARRAY['broken', 'defective', 'doesn''t work', 'doa', 'dead on arrival'], 8),
  ('product__howto', 'How-to / usage', ARRAY['how to', 'how do i', 'how can i', 'where do i'], 9),
  ('technical__troubleshooting', 'Technical troubleshooting', ARRAY['error', 'bug', 'not working', 'issue', 'problem', 'fix'], 10),
  ('compliance__privacy', 'Compliance / privacy', ARRAY['gdpr', 'delete my data', 'data deletion', 'privacy', 'dsar'], 11),
  ('feedback__praise', 'Feedback: Praise', ARRAY['thank you', 'great service', 'awesome', 'love your'], 12),
  ('feedback__complaint', 'Feedback: Complaint', ARRAY['complaint', 'terrible', 'worst', 'frustrated', 'angry'], 13),
  ('status__followup', 'Status / follow-up', ARRAY['any update', 'status', 'follow up', 'following up', 'when will'], 14),
  ('other_unclear', 'Other / unclear', ARRAY[]::TEXT[], 99)
ON CONFLICT (label) DO NOTHING;

-- RLS: allow service role full access; anon read-only for dashboard if needed
ALTER TABLE classification_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxonomy ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on classification_log" ON classification_log
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on taxonomy" ON taxonomy
  FOR ALL USING (auth.role() = 'service_role');
