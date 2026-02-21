"""Shopify catalog export. Uses Storefront API for canonical URLs (ToS-aligned)."""

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

# Storefront API GraphQL
PRODUCTS_QUERY = """
query GetProducts($cursor: String) {
  products(first: 50, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        handle
        title
        onlineStoreUrl
        vendor
        productType
        tags
        images(first: 20) {
          edges {
            node {
              url
            }
          }
        }
      }
    }
  }
}
"""


def fetch_products_storefront(store_domain: str, token: str) -> list[dict]:
    """Fetch all products with images via Storefront API. Respects rate limits."""
    url = f"https://{store_domain}/api/2024-01/graphql.json"
    headers = {"Content-Type": "application/json", "X-Shopify-Storefront-Access-Token": token}
    products = []
    cursor = None

    while True:
        variables = {"cursor": cursor} if cursor else {}
        payload = {"query": PRODUCTS_QUERY, "variables": variables}
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")

        edges = data["data"]["products"]["edges"]
        page_info = data["data"]["products"]["pageInfo"]

        for e in edges:
            node = e["node"]
            products.append({
                "id": node["id"],
                "handle": node["handle"],
                "title": node["title"],
                "online_store_url": node.get("onlineStoreUrl") or f"https://{store_domain}/products/{node['handle']}",
                "vendor": node.get("vendor"),
                "product_type": node.get("productType"),
                "tags": node.get("tags", []),
                "images": [img["node"]["url"] for img in node.get("images", {}).get("edges", [])],
            })

        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        time.sleep(0.6)  # ~2 req/sec

    return products


def fetch_from_sitemap(domain: str) -> list[dict]:
    """Fallback: parse sitemap.xml for product URLs when Storefront API unavailable."""
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


def load_catalog_from_file(path: Path) -> list[dict]:
    """Load catalog from JSON file (for bootstrapping when API not available)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("products", [])


def save_catalog_to_file(products: list[dict], path: Path) -> None:
    """Save catalog for caching / offline use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"products": products}, f, indent=2)
