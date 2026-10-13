# SyncSphere CRM — Hackathon MVP

A compact CRM dashboard for customer data management, WooCommerce order tracking, and event-driven communication workflow demos.

## Run locally

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Run `python -m venv .venv`
4. Activate it:
   - Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
   - macOS/Linux: `source .venv/bin/activate`
5. Run `pip install -r requirements.txt`
6. Run `python app.py`
7. Open `http://127.0.0.1:5000`

The app seeds sample data into `syncsphere.db` on first run. It is clearly marked Demo until you connect a store.

## Connect WooCommerce

In **Integrations**, enter:
- Store URL, e.g. `https://your-store.example`
- WooCommerce REST API consumer key (`ck_...`)
- WooCommerce REST API consumer secret (`cs_...`)

Create keys in WordPress Admin → WooCommerce → Settings → Advanced → REST API. Use a staging/test store and grant only the permissions needed. Click **Save & test sync**. The server fetches up to 100 customers and 100 orders per sync. This is intentionally capped for the hackathon MVP.

**Security:** credentials are stored in the local SQLite database for this demo. Do not expose this app publicly or use production credentials in an unsecured hackathon environment. For deployment, use environment secrets, HTTPS, authentication, pagination, rate limits, and a managed database.

## Webhooks

Endpoint: `POST /api/webhook/woocommerce`

Set the WooCommerce webhook delivery URL to `https://YOUR_PUBLIC_HOST/api/webhook/woocommerce`. The app logs incoming events. If you configure a webhook secret, set it locally in the database as `wc_webhook_secret` to enable HMAC verification. A public HTTPS URL is required for WooCommerce to reach a local machine; use a trusted tunnel only if permitted by your hackathon.

The webhook endpoint currently logs events; use **Sync** in Integrations to refresh full customer/order records. Communication workflow test runs are simulated and do not send real emails. Connect an email provider before claiming actual delivery.

## Scope

This is a hackathon MVP, not production-ready software. It has no login/role management, no email provider integration, and no background scheduler. Workflow toggles and test runs demonstrate configuration and event logging. Sample data is retained as demo data alongside WooCommerce records.
