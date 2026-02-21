# Zendesk Setup Guide

## 1. Create Custom Field: Reason for Contact

1. Go to **Admin** → **Objects and rules** → **Tickets** → **Fields**
2. Click **Add field**
3. Choose **Drop-down list**
4. Name: `Reason for contact`
5. Add options matching the taxonomy (use tag-style values for API compatibility):
   - `billing__duplicate_charge` → Display: "Billing: Duplicate charge"
   - `billing__refund_request` → Display: "Billing: Refund request"
   - `billing__payment_issue` → Display: "Billing: Payment issue"
   - `account__access` → Display: "Account: Access"
   - `account__cancel` → Display: "Account: Cancellation"
   - `shipping__delivery` → Display: "Shipping & delivery"
   - `returns__exchange` → Display: "Returns & exchange"
   - `product__defect` → Display: "Product defect"
   - `product__howto` → Display: "How-to / usage"
   - `technical__troubleshooting` → Display: "Technical troubleshooting"
   - `compliance__privacy` → Display: "Compliance / privacy"
   - `feedback__praise` → Display: "Feedback: Praise"
   - `feedback__complaint` → Display: "Feedback: Complaint"
   - `status__followup` → Display: "Status / follow-up"
   - `other_unclear` → Display: "Other / unclear"
6. Save and **note the field ID** (e.g. `12345678`). You'll need it for the Worker.

## 2. Create API Token

1. **Admin** → **Apps and integrations** → **APIs** → **Zendesk API**
2. Enable **Token access**
3. Add API token, copy it, and store securely (you won't see it again)

## 3. Create Webhook

1. **Admin** → **Apps and integrations** → **Webhooks**
2. **Create webhook**
3. **Endpoint URL**: `https://classify.yourdomain.com/webhook` (replace with your Worker URL)
4. **Request method**: POST
5. **Request format**: JSON
6. Save and note the webhook ID.

## 4. Create Trigger

1. **Admin** → **Objects and rules** → **Business rules** → **Triggers**
2. **Add trigger**
3. **Conditions**: `Ticket is` → `Created`
4. **Actions**:
   - **Notify webhook** → Select your webhook
   - Payload: default (Zendesk sends ticket event)
5. Save.

## 5. (Optional) Add "Needs triage" View

- Create a view for tickets where `Reason for contact` is empty or `Other / unclear` for manual triage.

---

## Image-to-Product Matcher (separate webhook)

For the **image-matcher** service (Zendesk attachment → shopaleena product URL):

1. **Admin** → **Apps and integrations** → **Webhooks** → **Create webhook**
2. **Endpoint URL**: `https://your-image-matcher-host/webhook/zendesk` (or `http://localhost:8000/webhook/zendesk` for dev)
3. **Request method**: POST, **Request format**: JSON
4. (Optional) Set **Signing secret**; add as `ZENDESK_WEBHOOK_SECRET` in image-matcher env for verification
5. **Add trigger**: **Conditions** → `Ticket` → `Updated` (or `Comment added` if available); **Actions** → Notify this webhook
