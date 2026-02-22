"""Product matcher: embed catalog, build index, match ticket images to products."""

from pathlib import Path

import numpy as np
import requests
from PIL import Image

from embeddings import build_faiss_index, embed_image, load_model, search
from preprocess import load_and_strip_exif


class ProductMatcher:
    """Match ticket images to products via CLIP embeddings + FAISS."""

    def __init__(
        self,
        catalog: list[dict],
        model_name: str = "ViT-B-32",
        pretrained: str = "laion2b_s34b_b79k",
        device: str = "cpu",
        max_catalog_images: int = 80,
        max_images_per_product: int = 1,
    ):
        self.model, self.preprocess, self.device = load_model(model_name, pretrained, device)
        self.catalog = catalog
        self.max_catalog_images = max(1, int(max_catalog_images))
        self.max_images_per_product = max(1, int(max_images_per_product))
        self.product_images: list[dict] = []
        self.product_id_to_idx: dict[str, list[int]] = {}
        self.index = None
        self._build_index()

    def _build_index(self):
        """Build product_image list and FAISS index from catalog."""
        vecs = []
        idx = 0
        for p in self.catalog:
            if idx >= self.max_catalog_images:
                break
            prod_id = p.get("id") or str(p.get("shopify_product_id", ""))
            url = p.get("online_store_url", "")
            for pos, img_url in enumerate((p.get("images", []) or [])[: self.max_images_per_product]):
                if idx >= self.max_catalog_images:
                    break
                if not img_url:
                    continue
                try:
                    img = self._fetch_image(img_url)
                    if img is None:
                        continue
                    v = embed_image(img, self.model, self.preprocess, self.device)
                    vecs.append(v)
                    self.product_images.append({
                        "product_id": prod_id,
                        "handle": p.get("handle", ""),
                        "title": p.get("title", ""),
                        "online_store_url": url,
                        "position": pos,
                        "image_url": img_url,
                    })
                    if prod_id not in self.product_id_to_idx:
                        self.product_id_to_idx[prod_id] = []
                    self.product_id_to_idx[prod_id].append(idx)
                    idx += 1
                except Exception:
                    continue
        if vecs:
            vectors = np.vstack(vecs).astype("float32")
            self.index = build_faiss_index(vectors)
        else:
            self.index = None

    def _fetch_image(self, url: str) -> Image.Image | None:
        try:
            r = requests.get(url, timeout=4, stream=True)
            r.raise_for_status()
            return Image.open(r.raw).convert("RGB")
        except Exception:
            return None

    def match(self, image_path: Path, top_k: int = 10) -> list[dict]:
        """
        Match a ticket image to products. Returns list of {product_id, url, score}.
        Aggregates by product (max score per product).
        """
        if self.index is None:
            return []
        img, _ = load_and_strip_exif(image_path)
        vec = embed_image(img, self.model, self.preprocess, self.device)
        scores, indices = search(self.index, vec, k=min(top_k * 2, len(self.product_images)))
        # aggregate by product
        seen = {}
        for sc, ix in zip(scores, indices):
            if ix < 0:
                continue
            pi = self.product_images[ix]
            pid = pi["product_id"]
            if pid not in seen or sc > seen[pid]["score"]:
                seen[pid] = {"product_id": pid, "url": pi["online_store_url"], "score": float(sc)}
        out = sorted(seen.values(), key=lambda x: -x["score"])[:top_k]
        return out


def load_catalog_for_matcher(catalog_path: Path | None, store_domain: str, token: str) -> list[dict]:
    """Load catalog from file only. Use /sync/catalog to populate (API or sitemap)."""
    if catalog_path and catalog_path.exists():
        from shopify_catalog import load_catalog_from_file
        return load_catalog_from_file(catalog_path)
    return []
