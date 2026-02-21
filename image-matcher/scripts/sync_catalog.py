#!/usr/bin/env python3
"""Sync catalog from Shopify Storefront API or sitemap. Writes cache/catalog.json."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

# Add parent for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings


def fetch_from_sitemap(domain: str) -> list[dict]:
    """Fallback: parse sitemap.xml for product URLs. One image per product (primary)."""
    url = f"https://{domain}/sitemap.xml"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9", "image": "http://www.google.com/schemas/sitemap-image/1.1"}
    products = []
    for sitemap in root.findall("sm:sitemap", ns):
        loc = sitemap.find("sm:loc", ns)
        if loc is None or "products" not in (loc.text or ""):
            continue
        sr = requests.get(loc.text, timeout=15)
        sr.raise_for_status()
        sroot = ET.fromstring(sr.content)
        for url_elem in sroot.findall("sm:url", ns):
            loc_elem = url_elem.find("sm:loc", ns)
            if loc_elem is None:
                continue
            product_url = loc_elem.text
            if "/products/" not in (product_url or ""):
                continue
            handle = product_url.rstrip("/").split("/products/")[-1].split("?")[0]
            img_url = None
            for img in url_elem.findall("image:image", ns):
                iloc = img.find("image:loc", ns)
                if iloc is not None and iloc.text:
                    img_url = iloc.text
                    break
            products.append({
                "id": f"sitemap:{handle}",
                "handle": handle,
                "title": handle.replace("-", " ").title(),
                "online_store_url": product_url,
                "images": [img_url] if img_url else [],
            })
    return products


def main():
    out_path = Path(settings.CACHE_DIR) / "catalog.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.SHOPIFY_STOREFRONT_TOKEN and settings.SHOPIFY_STORE_DOMAIN:
        from shopify_catalog import fetch_products_storefront, save_catalog_to_file
        products = fetch_products_storefront(settings.SHOPIFY_STORE_DOMAIN, settings.SHOPIFY_STOREFRONT_TOKEN)
        save_catalog_to_file(products, out_path)
        print(f"Synced {len(products)} products from Storefront API -> {out_path}")
    else:
        products = fetch_from_sitemap(settings.SHOPIFY_STORE_DOMAIN or "shopaleena.com")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"products": products}, f, indent=2)
        print(f"Synced {len(products)} products from sitemap -> {out_path}")


if __name__ == "__main__":
    main()
