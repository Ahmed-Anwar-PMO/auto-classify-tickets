"""Zendesk API: fetch ticket comments and attachments. Rate-limited, idempotent."""

import base64
import hashlib
import hmac
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# MIME types we treat as images
IMAGE_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp",
    "image/bmp", "image/tiff", "image/heic",
}


def verify_webhook_signature(body_bytes: bytes, timestamp: str, signature_b64: str, secret: str) -> bool:
    """Verify Zendesk webhook HMAC. Formula: base64(HMACSHA256(TIMESTAMP + BODY))."""
    if not secret:
        return False
    msg = timestamp.encode("utf-8") + body_bytes
    digest = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature_b64)


def _session(subdomain: str, email: str, token: str) -> requests.Session:
    s = requests.Session()
    s.auth = (f"{email}/token", token)
    s.headers["Content-Type"] = "application/json"
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def fetch_ticket_comments(subdomain: str, email: str, token: str, ticket_id: int) -> list[dict]:
    """Fetch all comments for a ticket. Each comment may have attachments."""
    base = f"https://{subdomain}.zendesk.com/api/v2"
    url = f"{base}/tickets/{ticket_id}/comments.json"
    out = []
    while url:
        r = requests.get(url, auth=(f"{email}/token", token), headers={"Content-Type": "application/json"})
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("comments", []))
        url = data.get("next_page")
        if url:
            time.sleep(0.5)  # rate limit
    return out


def iter_image_attachments(comments: list[dict]) -> list[dict]:
    """Yield attachment dicts that are images (content_type in IMAGE_TYPES)."""
    attachments = []
    for c in comments:
        for a in c.get("attachments", []):
            ct = (a.get("content_type") or "").lower()
            if ct in IMAGE_TYPES or (ct and ct.startswith("image/")):
                attachments.append({
                    "id": a.get("id"),
                    "file_name": a.get("file_name"),
                    "content_type": a.get("content_type"),
                    "content_url": a.get("content_url"),
                    "size": a.get("size"),
                    "comment_id": c.get("id"),
                })
    return attachments


def get_attachment_content_url(subdomain: str, email: str, token: str, ticket_id: int, attachment_id: int) -> str | None:
    """Find content_url for an attachment by ID. Used by labeling UI."""
    comments = fetch_ticket_comments(subdomain, email, token, ticket_id)
    for c in comments:
        for a in c.get("attachments", []):
            if a.get("id") == attachment_id:
                return a.get("content_url")
    return None


def add_internal_note(subdomain: str, email: str, token: str, ticket_id: int, body: str) -> bool:
    """Add internal (private) note to ticket. Returns True on success."""
    base = f"https://{subdomain}.zendesk.com/api/v2"
    url = f"{base}/tickets/{ticket_id}.json"
    payload = {
        "ticket": {
            "comment": {"body": body, "public": False}
        }
    }
    r = requests.put(url, auth=(f"{email}/token", token), json=payload, headers={"Content-Type": "application/json"}, timeout=15)
    if not r.ok:
        return False
    return True


def download_attachment(content_url: str, email: str, token: str, dest_path: Path) -> Path | None:
    """
    Download attachment. Zendesk attachment URLs may require auth.
    Returns path if successful, None on failure.
    """
    try:
        r = requests.get(
            content_url,
            auth=(f"{email}/token", token),
            headers={"Content-Type": "application/json"},
            timeout=30,
            stream=True,
        )
        r.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return dest_path
    except Exception:
        return None
