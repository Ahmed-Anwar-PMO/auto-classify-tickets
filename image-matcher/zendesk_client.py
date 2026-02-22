"""Zendesk API: fetch ticket comments and attachments. Rate-limited, idempotent."""

import base64
import hashlib
import hmac
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# MIME types we treat as images
IMAGE_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp",
    "image/bmp", "image/tiff", "image/heic",
}
IMAGE_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic"
)
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)


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


def fetch_ticket_audits(subdomain: str, email: str, token: str, ticket_id: int) -> list[dict]:
    """Fetch all audits/events for a ticket."""
    base = f"https://{subdomain}.zendesk.com/api/v2"
    url = f"{base}/tickets/{ticket_id}/audits.json"
    out = []
    while url:
        r = requests.get(url, auth=(f"{email}/token", token), headers={"Content-Type": "application/json"})
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("audits", []))
        url = data.get("next_page")
        if url:
            time.sleep(0.5)
    return out


def _normalize_content_url(url: str) -> str:
    if not url:
        return ""
    return url.strip().strip("()[]<>{}\"'`")


def _extract_urls_from_text(text: str) -> list[str]:
    if not text:
        return []
    return [_normalize_content_url(u) for u in URL_PATTERN.findall(text)]


def _collect_urls(obj, out: set[str]) -> None:
    if isinstance(obj, dict):
        for value in obj.values():
            _collect_urls(value, out)
        return
    if isinstance(obj, list):
        for value in obj:
            _collect_urls(value, out)
        return
    if isinstance(obj, str):
        out.update(_extract_urls_from_text(obj))


def _is_image_candidate_url(url: str) -> bool:
    parsed = urlsplit(url)
    path = (parsed.path or "").lower()
    if "/sc/attachments/" in path:
        return True
    return any(path.endswith(ext) for ext in IMAGE_EXTENSIONS)


def _is_non_ticket_asset(url: str) -> bool:
    parsed = urlsplit(url)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    if "/sc/attachments/" in path:
        return False
    if "static.zdassets.com" in host and "default_avatar" in path:
        return True
    return False


def _stable_bigint_from_url(url: str) -> int:
    digest = hashlib.sha256(url.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
    return value if value > 0 else 1


def _safe_int(value, fallback: int) -> int:
    try:
        number = int(value)
        if number > 0:
            return number
    except (TypeError, ValueError):
        pass
    return fallback


def _build_url_candidate(content_url: str, comment_id: int | None, source: str) -> dict:
    content_url = _normalize_content_url(content_url)
    attachment_id = _stable_bigint_from_url(content_url)
    comment_hint = _safe_int(comment_id, attachment_id)
    return {
        "id": attachment_id,
        "file_name": Path(urlsplit(content_url).path).name or f"{attachment_id}.jpg",
        "content_type": None,
        "content_url": content_url,
        "size": None,
        "comment_id": comment_hint,
        "source": source,
    }


def iter_image_attachments(comments: list[dict], audits: list[dict] | None = None) -> list[dict]:
    """Build unified image candidates from attachments + comment/audit URLs."""
    attachments = []
    seen_urls: set[str] = set()

    def maybe_add(candidate: dict) -> None:
        url = _normalize_content_url(candidate.get("content_url") or "")
        if not url:
            return
        if not _is_image_candidate_url(url):
            return
        if _is_non_ticket_asset(url):
            return
        if url in seen_urls:
            return
        seen_urls.add(url)
        candidate["content_url"] = url
        attachments.append(candidate)

    # 1) Structured comment attachments
    for c in comments:
        for a in c.get("attachments", []):
            ct = (a.get("content_type") or "").lower()
            url = _normalize_content_url(a.get("content_url") or "")
            if not url:
                continue
            is_image_ct = ct in IMAGE_TYPES or (ct and ct.startswith("image/"))
            if not is_image_ct and not _is_image_candidate_url(url):
                continue
            attachment_id = _safe_int(a.get("id"), _stable_bigint_from_url(url))
            comment_id = _safe_int(c.get("id"), attachment_id)
            maybe_add({
                "id": attachment_id,
                "file_name": a.get("file_name"),
                "content_type": a.get("content_type"),
                "content_url": url,
                "size": a.get("size"),
                "comment_id": comment_id,
                "source": "comment_attachment",
            })

    # 2) Comment body/html/plain URLs
    for c in comments:
        comment_id = _safe_int(c.get("id"), 1)
        for field in ("body", "html_body", "plain_body"):
            for url in _extract_urls_from_text(c.get(field) or ""):
                maybe_add(_build_url_candidate(url, comment_id, f"comment_{field}_url"))

    # 3) Audit event URLs (chat payloads often place attachments here)
    for audit in audits or []:
        audit_id = _safe_int(audit.get("id"), 1)
        for ev in audit.get("events", []):
            event_id = _safe_int(ev.get("id"), audit_id)
            urls: set[str] = set()
            _collect_urls(ev, urls)
            source = f"audit_{(ev.get('type') or 'event').lower()}_url"
            for url in urls:
                maybe_add(_build_url_candidate(url, event_id, source))

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
