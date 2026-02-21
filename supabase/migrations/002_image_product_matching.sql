-- Image-to-Product-URL matching system (per design doc)
-- ticket_image: Zendesk attachment metadata + embeddings reference
-- product: shopaleena catalog from Shopify
-- product_image: catalog images with embeddings
-- image_prediction_log: predictions for monitoring + feedback

CREATE TABLE IF NOT EXISTS product (
  id BIGSERIAL PRIMARY KEY,
  shopify_product_id TEXT UNIQUE NOT NULL,
  handle TEXT NOT NULL,
  title TEXT NOT NULL,
  online_store_url TEXT NOT NULL,
  vendor TEXT,
  product_type TEXT,
  tags TEXT[] DEFAULT '{}',
  published_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS product_image (
  id BIGSERIAL PRIMARY KEY,
  shopify_product_id TEXT NOT NULL,
  image_url TEXT NOT NULL,
  position INT NOT NULL DEFAULT 0,
  sha256_hex TEXT,
  phash TEXT,
  embedding_model TEXT,
  embedding_ref TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(shopify_product_id, position)
);

CREATE TABLE IF NOT EXISTS ticket_image (
  id BIGSERIAL PRIMARY KEY,
  zendesk_ticket_id BIGINT NOT NULL,
  zendesk_comment_id BIGINT NOT NULL,
  zendesk_attachment_id BIGINT NOT NULL,
  attachment_content_url TEXT NOT NULL,
  downloaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sha256_hex TEXT,
  phash TEXT,
  width INT,
  height INT,
  format TEXT,
  exif_stripped BOOLEAN DEFAULT FALSE,
  ocr_text TEXT,
  embedding_model TEXT,
  embedding_ref TEXT,
  ground_truth_product_id TEXT,
  ground_truth_product_url TEXT,
  label_source TEXT CHECK (label_source IN ('manual', 'assisted', 'inferred')),
  labeler_id TEXT,
  labeled_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(zendesk_attachment_id)
);

CREATE TABLE IF NOT EXISTS image_prediction_log (
  id BIGSERIAL PRIMARY KEY,
  zendesk_attachment_id BIGINT NOT NULL,
  zendesk_ticket_id BIGINT NOT NULL,
  predicted_product_id TEXT,
  predicted_product_url TEXT,
  top_k JSONB NOT NULL DEFAULT '[]',
  confidence NUMERIC(5,4),
  accepted BOOLEAN,
  overridden_product_id TEXT,
  model_version TEXT NOT NULL DEFAULT 'openclip-vit-b32',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_product_handle ON product(handle);
CREATE INDEX IF NOT EXISTS idx_product_image_product ON product_image(shopify_product_id);
CREATE INDEX IF NOT EXISTS idx_ticket_image_ticket ON ticket_image(zendesk_ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_image_attachment ON ticket_image(zendesk_attachment_id);
CREATE INDEX IF NOT EXISTS idx_image_prediction_attachment ON image_prediction_log(zendesk_attachment_id);
CREATE INDEX IF NOT EXISTS idx_image_prediction_ticket ON image_prediction_log(zendesk_ticket_id);
CREATE INDEX IF NOT EXISTS idx_image_prediction_created ON image_prediction_log(created_at);

-- RLS
ALTER TABLE product ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_image ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_image ENABLE ROW LEVEL SECURITY;
ALTER TABLE image_prediction_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on product" ON product
  FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access on product_image" ON product_image
  FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access on ticket_image" ON ticket_image
  FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access on image_prediction_log" ON image_prediction_log
  FOR ALL USING (auth.role() = 'service_role');
