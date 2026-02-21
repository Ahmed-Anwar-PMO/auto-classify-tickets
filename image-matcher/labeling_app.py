"""
Assisted labeling UI: review image_prediction_log, accept/override product match.
Shows ticket image + top-k suggestions; stores ground truth for evaluation.
"""

import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import settings
from supabase_client import get_client, fetch_unreviewed_predictions, update_prediction_review, update_ticket_image_ground_truth
from zendesk_client import get_attachment_content_url, download_attachment


def fetch_image_for_prediction(pred: dict) -> bytes | None:
    """Download ticket attachment image from Zendesk."""
    if not settings.zendesk_ok:
        return None
    ticket_id = pred["zendesk_ticket_id"]
    att_id = pred["zendesk_attachment_id"]
    content_url = get_attachment_content_url(
        settings.ZENDESK_SUBDOMAIN,
        settings.ZENDESK_EMAIL,
        settings.ZENDESK_API_TOKEN,
        ticket_id,
        att_id,
    )
    if not content_url:
        return None
    dest = Path(tempfile.gettempdir()) / f"label_{att_id}.jpg"
    path = download_attachment(
        content_url,
        settings.ZENDESK_EMAIL,
        settings.ZENDESK_API_TOKEN,
        dest,
    )
    if path:
        data = path.read_bytes()
        path.unlink(missing_ok=True)
        return data
    return None


def main():
    st.set_page_config(page_title="Image Product Labeler", layout="wide")
    st.title("Image → Product URL Labeling")

    supabase = get_client()
    if not supabase:
        st.error("Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY.")
        return

    if not settings.zendesk_ok:
        st.warning("Zendesk not configured. Images will not load; you can still review top-k.")

    limit = st.sidebar.number_input("Max predictions to fetch", min_value=5, max_value=200, value=30)
    if st.sidebar.button("Refresh"):
        st.rerun()

    predictions = fetch_unreviewed_predictions(supabase, limit=limit)
    if not predictions:
        st.info("No unreviewed predictions. Run backfill or wait for webhook processing.")
        return

    st.sidebar.metric("Unreviewed", len(predictions))

    for pred in predictions:
        with st.container():
            col_img, col_choices = st.columns([1, 2])

            with col_img:
                st.caption(f"Ticket #{pred['zendesk_ticket_id']} · Attachment {pred['zendesk_attachment_id']}")
                img_bytes = fetch_image_for_prediction(pred)
                if img_bytes:
                    st.image(img_bytes, use_container_width=True)
                else:
                    st.write("_Image unavailable (Zendesk auth?)_")
                st.caption(f"Confidence: {pred.get('confidence', 0):.2f}")

            with col_choices:
                top_k = pred.get("top_k") or []
                if not top_k:
                    st.write("_No candidates_")
                else:
                    for i, c in enumerate(top_k):
                        url = c.get("url", "")
                        pid = c.get("product_id", "")
                        score = c.get("score", 0)
                        label = f"✓ {url[:55]}... ({score:.2f})" if len(url) > 55 else f"✓ {url} ({score:.2f})"
                        if st.button(label, key=f"btn_{pred['id']}_{i}"):
                            update_prediction_review(
                                supabase, pred["id"], accepted=True,
                                overridden_product_id=pid, overridden_product_url=url,
                            )
                            update_ticket_image_ground_truth(
                                supabase, pred["zendesk_attachment_id"], pid, url, label_source="assisted",
                            )
                            st.success(f"Accepted: {url[:60]}...")
                            st.rerun()
                    if st.button("✗ None of these", key=f"none_{pred['id']}"):
                        update_prediction_review(supabase, pred["id"], accepted=False)
                        st.success("Marked as 'none of these'")
                        st.rerun()

            st.divider()


if __name__ == "__main__":
    main()
