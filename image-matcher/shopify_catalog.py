"""Shopify catalog export. Uses Storefront API for canonical URLs (ToS-aligned)."""

import json
import time
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
