"""Bake catalog and warm model cache during Render build."""

import json
import os
import sys
from pathlib import Path

# Ensure image-matcher is on path (when run as scripts/bake_catalog.py)
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "catalog.json"
MODEL_CACHE = ROOT / "cache" / "model-cache"
HF_HOME = MODEL_CACHE / "hf"
TORCH_HOME = MODEL_CACHE / "torch"
OPENCLIP_CACHE = MODEL_CACHE / "openclip"


def _ensure_model_cache_env() -> None:
    MODEL_CACHE.mkdir(parents=True, exist_ok=True)
    HF_HOME.mkdir(parents=True, exist_ok=True)
    TORCH_HOME.mkdir(parents=True, exist_ok=True)
    OPENCLIP_CACHE.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(HF_HOME))
    os.environ.setdefault("TORCH_HOME", str(TORCH_HOME))
    os.environ.setdefault("OPENCLIP_CACHE_DIR", str(OPENCLIP_CACHE))


def _warm_model_cache() -> None:
    from config import settings

    if (settings.MATCHER_BACKEND or "hash").strip().lower() != "clip":
        print("Skipping OpenCLIP cache warmup (matcher backend is not clip)")
        return

    from embeddings import load_model

    print(
        "Warming OpenCLIP cache "
        f"(model={settings.EMBEDDING_MODEL}, pretrained={settings.EMBEDDING_PRETRAINED})"
    )
    model, preprocess, device = load_model(
        settings.EMBEDDING_MODEL,
        settings.EMBEDDING_PRETRAINED,
        "cpu",
    )
    del model, preprocess, device
    print("OpenCLIP cache warm complete")


def _write_fallback_catalog() -> None:
    fallback = [{
        "id": "fallback",
        "handle": "fallback",
        "title": "Fallback",
        "online_store_url": "https://shopaleena.com/",
        "images": [],
    }]
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(fallback, f)
    print("Wrote minimal fallback catalog")


def main():
    try:
        from shopify_catalog import fetch_from_sitemap, save_catalog_to_file

        _ensure_model_cache_env()
        catalog = fetch_from_sitemap("shopaleena.com")
        save_catalog_to_file(catalog, OUT)
        print(f"Baked catalog: {len(catalog)} products -> {OUT}")
    except Exception as e:
        print(f"Bake failed: {e}", file=sys.stderr)
        _write_fallback_catalog()

    try:
        _warm_model_cache()
    except Exception as e:
        # Keep deploy green even if model warmup fails; runtime still has timeout guards.
        print(f"Model cache warmup skipped: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
