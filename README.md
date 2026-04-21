# Coffee leads: n8n + Google Sheet + Apps Script + static UI

This folder contains:

- [`Leads-Finder_Workflow.json`](Leads-Finder_Workflow.json) — import into [n8n](https://n8n.io). The workflow calls [Serper](https://serper.dev), parses directory hits, optionally downloads **PDF** sources and extracts text, enriches contacts, and appends rows to Google Sheets (including a stable **`LeadId`**).
- [`gas/LeadsApi.gs`](gas/LeadsApi.gs) — paste into the Google Sheet’s Apps Script project. Deploy as a **Web app** and use **JSONP** from the browser (Apps Script cannot attach CORS headers to JSON responses).
- [`web/`](web/) — static dashboard: POSTs only `{ country, categories, sources }` through a **serverless proxy** (so your n8n webhook URL stays off the client). Loads and updates lead rows via the Apps Script URL + token.

## n8n setup

1. **Import** `Leads-Finder_Workflow.json`.
2. **Environment**: set `SERPER_API_KEY` on the n8n server (recommended). For a one-off test you may include `"serperKey"` in the webhook JSON body; production should rely on the env var only. For **PDF** source URLs, set **`PDF_CO_API_KEY`** ([PDF.co](https://pdf.co/) — see [PDF to Text API](https://developer.pdf.co/api/pdf-to-text/)) or pass `pdfCoApiKey` in the body for testing.
3. **Google Sheets**: connect OAuth in the **Google Sheets – Append Row** node and point it at your spreadsheet. Row **1** must include headers matching the node mapping, including **`LeadId`** as the first column (recommended) or at least present somewhere in row 1.
4. **Webhook URL**: copy the production URL from the Webhook node and store it as `N8N_WEBHOOK_URL` in Netlify or Vercel (see below), not in the static site.
5. **Request body** (from the proxy or `curl`):

```json
{
  "country": "Brazil",
  "categories": ["importer", "exporter", "broker"],
  "sources": ["sca", "nca", "gafta"]
}
```

## Google Apps Script

1. Open your Sheet → **Extensions** → **Apps Script**. Paste [`gas/LeadsApi.gs`](gas/LeadsApi.gs).
2. **Project settings** → **Script properties** → add `LEADS_API_TOKEN` (long random string).
3. **Deploy** → **New deployment** → type **Web app** → Execute as **Me** → Who has access **Anyone** (the token still gates data).
4. Copy the **Web app URL** (ends with `/exec`) into `web/config.js` as `gasBaseUrl`, and the same token as `gasToken`.

## Netlify (static + proxy)

1. Connect this repo or run `netlify deploy` from the project root ([`netlify.toml`](netlify.toml) publishes `web/` and builds functions from `netlify/functions`).
2. In the Netlify UI → **Site settings** → **Environment variables** → add `N8N_WEBHOOK_URL` = your full n8n webhook POST URL.
3. Copy `web/config.sample.js` to `web/config.js` and set:
   - `proxyTriggerUrl` — `https://<your-site>.netlify.app/.netlify/functions/trigger-leads`
   - `gasBaseUrl`, `gasToken` — from the Apps Script steps above.

## Vercel (static + proxy)

1. Deploy the repository root so the [`api/trigger-leads.js`](api/trigger-leads.js) serverless route is included.
2. In Vercel → **Settings** → **Environment variables** → `N8N_WEBHOOK_URL`.
3. Configure the site so static files are served from `web/` (set **Output directory** / root accordingly in the Vercel project), or move `web/index.html` to the public root if you prefer a flatter layout.
4. Set `proxyTriggerUrl` in `web/config.js` to `https://<your-domain>/api/trigger-leads`.

## Regenerating the workflow JSON

[`scripts/patch_workflow.py`](scripts/patch_workflow.py) reapplies structural fixes (normalize node, Serper JSON bodies, Split-in-batches wiring, PDF branch, `LeadId`). Run:

```bash
python scripts/patch_workflow.py
```

## Notes

- **Browser → n8n**: direct `fetch` to the n8n host often fails **CORS**; the included proxy exists to forward POSTs server-side.
- **Browser → Apps Script**: `LeadsApi.gs` uses **JSONP** (`?callback=…`) because standard JSON responses from Web Apps do not support configurable CORS headers.
- **PDFs**: when a lead’s `sourceUrl` ends with `.pdf`, the workflow calls **PDF.co** `POST /v1/pdf/convert/to/text` with `inline: true` (URL + OCR-friendly extraction per [their docs](https://developer.pdf.co/api/pdf-to-text/)), then **Code – PDF Contacts** regex-extracts emails, phones, and social links before appending to the sheet. Failed API calls set `Status` to `pdf-error`.
