"""Configuration from env. Reuses same vars as worker (ZENDESK_*, SUPABASE_*)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Zendesk (same as worker)
    ZENDESK_SUBDOMAIN: str = ""
    ZENDESK_EMAIL: str = ""
    ZENDESK_API_TOKEN: str = ""

    # Webhook signing (Zendesk webhook secret)
    ZENDESK_WEBHOOK_SECRET: str = ""

    # Supabase (same as worker)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # Shopify (Storefront API for shopaleena.com)
    SHOPIFY_STORE_DOMAIN: str = "shopaleena.com"
    SHOPIFY_STOREFRONT_TOKEN: str = ""

    # Zendesk write-back (add internal note with product URL when confident)
    ZENDESK_WRITE_BACK_ENABLED: bool = False
    ZENDESK_WRITE_BACK_CONFIDENCE: float = 0.75

    # Embedding model
    EMBEDDING_MODEL: str = "ViT-B-32"
    EMBEDDING_PRETRAINED: str = "laion2b_s34b_b79k"
    MATCHER_MAX_CATALOG_IMAGES: int = 24
    MATCHER_MAX_IMAGES_PER_PRODUCT: int = 1

    # Paths
    DATA_DIR: str = "./data"
    CACHE_DIR: str = "./cache"
    MODEL_CACHE_DIR: str = "./cache/model-cache"
    EMBEDDINGS_DIR: str = "./data/embeddings"

    @property
    def zendesk_ok(self) -> bool:
        return bool(self.ZENDESK_SUBDOMAIN and self.ZENDESK_EMAIL and self.ZENDESK_API_TOKEN)

    @property
    def supabase_ok(self) -> bool:
        return bool(self.SUPABASE_URL and self.SUPABASE_SERVICE_KEY)


settings = Settings()
