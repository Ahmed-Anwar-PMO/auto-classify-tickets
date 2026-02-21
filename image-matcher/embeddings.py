"""OpenCLIP image embeddings + FAISS nearest-neighbor search."""

from pathlib import Path

import numpy as np
import open_clip
import torch
from PIL import Image


def load_model(model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k", device: str = "cpu"):
    """Load OpenCLIP model and preprocess. CPU ok for moderate volume."""
    model, _, preprocess = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
    model.eval().to(device)
    return model, preprocess, device


def embed_image(pil_img: Image.Image, model, preprocess, device: str) -> np.ndarray:
    """Embed single image. Returns L2-normalized 512-dim vector (float32)."""
    x = preprocess(pil_img).unsqueeze(0).to(device)
    with torch.no_grad():
        v = model.encode_image(x)
        v = v / v.norm(dim=-1, keepdim=True)
    return v.cpu().numpy().astype("float32")[0]


def embed_images(pil_images: list[Image.Image], model, preprocess, device: str, batch_size: int = 32) -> np.ndarray:
    """Embed batch of images."""
    vecs = []
    for i in range(0, len(pil_images), batch_size):
        batch = pil_images[i : i + batch_size]
        tensors = torch.stack([preprocess(img) for img in batch]).to(device)
        with torch.no_grad():
            v = model.encode_image(tensors)
            v = v / v.norm(dim=-1, keepdim=True)
        vecs.append(v.cpu().numpy().astype("float32"))
    return np.vstack(vecs)


def build_faiss_index(vectors: np.ndarray):
    """Build FAISS index for cosine similarity (inner product on normalized vectors)."""
    import faiss
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    return index


def search(index, query_vec: np.ndarray, k: int = 10):
    """Search FAISS index. query_vec must be normalized. Returns (scores, indices)."""
    import faiss
    if query_vec.ndim == 1:
        query_vec = query_vec.reshape(1, -1)
    scores, indices = index.search(query_vec.astype("float32"), k)
    return scores[0], indices[0]
