"""Image preprocessing: type filter, EXIF strip, dedup hashes."""

import hashlib
from io import BytesIO
from pathlib import Path

import imagehash
from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic"}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def phash_hex(pil_img: Image.Image) -> str:
    return str(imagehash.phash(pil_img))


def load_and_strip_exif(path: Path) -> tuple[Image.Image, bool]:
    """Load image, strip EXIF. Returns (PIL.Image, exif_was_stripped)."""
    img = Image.open(path).convert("RGB")
    exif_stripped = hasattr(img, "getexif") and img.getexif() is not None
    if exif_stripped:
        data = BytesIO()
        img.save(data, format="PNG")
        data.seek(0)
        img = Image.open(data).convert("RGB")
    return img, exif_stripped


def is_image_path(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def get_image_info(pil_img: Image.Image) -> dict:
    return {"width": pil_img.width, "height": pil_img.height, "format": pil_img.format or "unknown"}
