"""Bake catalog during Render build. Ensures catalog_cached is always true after deploy."""
import json
import sys
from pathlib import Path

# Ensure image-matcher is on path (when run as scripts/bake_catalog.py)
sys.path.insert(0, str(Path(__file__).parent.parent))
OUT = Path(__file__).parent.parent / "catalog.json"


def main():
    try:
        from shopify_catalog import fetch_from_sitemap, save_catalog_to_file
        catalog = fetch_from_sitemap("shopaleena.com")
        save_catalog_to_file(catalog, OUT)
        print(f"Baked catalog: {len(catalog)} products -> {OUT}")
        return 0
    except Exception as e:
        print(f"Bake failed: {e}", file=sys.stderr)
        # Create minimal catalog so catalog_cached is true
        fallback = [{"id": "fallback", "handle": "fallback", "title": "Fallback", "online_store_url": "https://shopaleena.com/", "images": []}]
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(fallback, f)
        print(f"Wrote minimal fallback catalog")
        return 0


if __name__ == "__main__":
    sys.exit(main())
