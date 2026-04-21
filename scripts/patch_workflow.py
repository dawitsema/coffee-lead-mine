"""Patch Leads-Finder_Workflow.json: normalize node, Serper JSON, split wiring, LeadId, PDF.co branch."""
import json
import pathlib
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
WF_PATH = ROOT / "Leads-Finder_Workflow.json"

NORMALIZE_JS = r"""const root = $json.body !== undefined ? $json.body : $json;
const country = String(root.country || '').trim();
let categories = root.categories;
if (!Array.isArray(categories) || categories.length === 0) {
  categories = ['importer', 'exporter', 'broker'];
}
let sources = root.sources;
if (!Array.isArray(sources) || sources.length === 0) {
  sources = ['sca', 'nca', 'gafta'];
}
const serperKey = String($env.SERPER_API_KEY || root.serperKey || '').trim();
const pdfCoApiKey = String($env.PDF_CO_API_KEY || root.pdfCoApiKey || '').trim();
if (!country) {
  throw new Error('country is required in webhook JSON body');
}
if (!serperKey) {
  throw new Error('Set SERPER_API_KEY on the n8n host or pass serperKey in the body for testing');
}
return [{
  json: {
    country,
    categories,
    sources,
    triggeredAt: new Date().toISOString(),
    serperKey,
    pdfCoApiKey,
  },
}];"""

PARSE_LEADS_JS = r"""// Parse Serper organic results; filter by sources/categories; assign leadsId
const items = $input.all();
const config = $('Normalize Variables').first().json;
const country = config.country;
const sourcesFilter = new Set((config.sources || []).map((s) => String(s).toLowerCase()));
const categoriesFilter = new Set((config.categories || []).map((s) => String(s).toLowerCase()));

const SOURCE_MAP = {
  'members.sca.coffee': 'SCA Directory',
  'sca.coffee': 'SCA Directory',
  'ncausa.org': 'NCA Member List',
  'gafta.com': 'GAFTA Approved List',
};

const SECTOR_MAP = {
  'SCA Directory': 'coffee',
  'NCA Member List': 'coffee',
  'GAFTA Approved List': 'cereal',
};

const ROLE_KEYWORDS = [
  { keywords: ['import'], role: 'Importer' },
  { keywords: ['export'], role: 'Exporter' },
  { keywords: ['broker', 'brokerage'], role: 'Broker' },
  { keywords: ['trader', 'trading', 'commodity'], role: 'Commodity Trader' },
  { keywords: ['freight', 'forwarder'], role: 'Freight Forwarder' },
  { keywords: ['roaster', 'roasting'], role: 'Roaster' },
  { keywords: ['distributor'], role: 'Distributor' },
];

function sourceAllowed(sourceLabel) {
  if (!sourcesFilter.size) return true;
  if (sourcesFilter.has('sca') && sourceLabel === 'SCA Directory') return true;
  if (sourcesFilter.has('nca') && sourceLabel === 'NCA Member List') return true;
  if (sourcesFilter.has('gafta') && sourceLabel === 'GAFTA Approved List') return true;
  return false;
}

function roleMatchesCategories(role) {
  if (!categoriesFilter.size) return true;
  const r = (role || '').toLowerCase();
  for (const c of categoriesFilter) {
    if (c === 'importer' && r.includes('import')) return true;
    if (c === 'exporter' && r.includes('export')) return true;
    if (c === 'broker' && r.includes('broker')) return true;
    if (c === 'grain-trader' && (r.includes('trader') || r.includes('commodity'))) return true;
    if (c === 'freight-forwarder' && (r.includes('freight') || r.includes('forwarder'))) return true;
  }
  return false;
}

function newLeadsId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

const leads = [];

for (const item of items) {
  const results = item.json.organic || item.json.organic_results || [];

  for (const r of results) {
    const url = r.link || '';
    const title = r.title || '';
    const snip = r.snippet || '';
    const full = (title + ' ' + snip).toLowerCase();

    let source = 'Unknown';
    for (const [domain, label] of Object.entries(SOURCE_MAP)) {
      if (url.includes(domain)) {
        source = label;
        break;
      }
    }
    if (source === 'Unknown') continue;
    if (!sourceAllowed(source)) continue;

    const sector = SECTOR_MAP[source] || 'coffee';

    let role = 'Import-Export Broker';
    for (const { keywords, role: r2 } of ROLE_KEYWORDS) {
      if (keywords.some((k) => full.includes(k))) {
        role = r2;
        break;
      }
    }
    if (!roleMatchesCategories(role)) continue;

    const company = title.split(/[-|–]/)[0].trim() || title;
    if (leads.find((l) => l.company === company)) continue;

    leads.push({
      leadsId: newLeadsId(),
      company,
      country,
      sector,
      role,
      source,
      sourceUrl: url,
      snippet: snip,
      email: '',
      phone: '',
      linkedin: '',
      twitter: '',
      whatsapp: '',
      enrichedAt: '',
      status: 'pending',
    });
  }
}

if (leads.length === 0) {
  const ph = [
    { sector: 'coffee', role: 'Exporter', source: 'SCA Directory' },
    { sector: 'coffee', role: 'Importer', source: 'NCA Member List' },
    { sector: 'coffee', role: 'Broker', source: 'SCA Directory' },
    { sector: 'cereal', role: 'Exporter', source: 'GAFTA Approved List' },
    { sector: 'cereal', role: 'Broker', source: 'GAFTA Approved List' },
    { sector: 'cereal', role: 'Commodity Trader', source: 'GAFTA Approved List' },
  ];
  for (const p of ph) {
    if (!sourceAllowed(p.source)) continue;
    if (!roleMatchesCategories(p.role)) continue;
    leads.push({
      leadsId: newLeadsId(),
      company: `${country} ${p.sector === 'coffee' ? 'Coffee' : 'Grain'} ${p.role} Co.`,
      country,
      sector: p.sector,
      role: p.role,
      source: p.source,
      sourceUrl: '',
      snippet: '',
      email: '',
      phone: '',
      linkedin: '',
      twitter: '',
      whatsapp: '',
      enrichedAt: '',
      status: 'pending',
    });
  }
}

return leads.map((l) => ({ json: l }));"""

EXTRACT_CONTACTS_JS = r"""// Email Search -> input 0; Social & Phone -> input 1
const emailData = $('Serper – Email Search').first().json;
const socialData = $('Serper – Social & Phone Search').first().json;
const lead = { ...$('Split In Batches').first().json };

const EMAIL_RE = /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g;
const emailResults = emailData.organic || emailData.organic_results || [];
const emailText = emailResults.map((r) => (r.title || '') + ' ' + (r.snippet || '')).join(' ');
const emailRaw = emailText.match(EMAIL_RE) || [];
const blocklist = ['example.com', 'sentry.io', 'wixpress.com', 'placeholder', 'schema.org', 'w3.org', 'googleapis.com'];
lead.email = emailRaw.filter((e) => !blocklist.some((b) => e.includes(b)))[0] || '';

const PHONE_RE = /(?:\+?[0-9]{1,3}[\s\-.]?)?(?:\(?[0-9]{1,4}\)?[\s\-.]?){2,}[0-9]{4,}/g;
const phoneFromEmail = emailResults.map((r) => r.snippet || '').join(' ');
const phoneRawEmail = phoneFromEmail.match(PHONE_RE) || [];

const socialResults = socialData.organic || socialData.organic_results || [];
const socialText = socialResults.map((r) => (r.title || '') + ' ' + (r.snippet || '') + ' ' + (r.link || '')).join(' ');
const phoneRawSocial = socialText.match(PHONE_RE) || [];

lead.phone = phoneRawEmail[0] || phoneRawSocial[0] || '';

for (const r of socialResults) {
  const url = (r.link || '').toLowerCase();
  if (!lead.linkedin && url.includes('linkedin.com/company')) lead.linkedin = r.link;
  if (!lead.twitter && (url.includes('twitter.com') || url.includes('x.com'))) lead.twitter = r.link;
  if (!lead.whatsapp && url.includes('wa.me')) lead.whatsapp = r.link;
}

lead.enrichedAt = new Date().toISOString();
lead.status = 'enriched';

return [{ json: lead }];"""

PDF_CONTACTS_JS = r"""const lead = { ...$('Split In Batches').first().json };
const res = $input.first().json;

if (res.error === true || Number(res.status) >= 400) {
  lead.snippet = String(res.message || res.body || 'PDF.co request failed');
  lead.status = 'pdf-error';
  lead.enrichedAt = new Date().toISOString();
  return [{ json: lead }];
}

const text = String(res.body != null ? res.body : res.text || '');

const EMAIL_RE = /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g;
const PHONE_RE = /(?:\+?[0-9]{1,3}[\s\-.]?)?(?:\(?[0-9]{1,4}\)?[\s\-.]?){2,}[0-9]{4,}/g;
const emails = text.match(EMAIL_RE) || [];
const blocklist = ['example.com', 'sentry.io', 'wixpress.com', 'schema.org', 'w3.org', 'googleapis.com'];
lead.email = emails.filter((e) => !blocklist.some((b) => e.includes(b)))[0] || '';
const phones = text.match(PHONE_RE) || [];
lead.phone = phones[0] || '';

const li = text.match(/https?:\/\/(?:www\.)?linkedin\.com\/(?:company|in)\/[a-zA-Z0-9\-_%]+/gi);
lead.linkedin = li ? li[0] : '';
const tw = text.match(/https?:\/\/(?:www\.)?(?:twitter\.com|x\.com)\/[a-zA-Z0-9_]+/gi);
lead.twitter = tw ? tw[0] : '';
const wa = text.match(/https?:\/\/wa\.me\/[0-9]+/gi);
lead.whatsapp = wa ? wa[0] : '';

lead.enrichedAt = new Date().toISOString();
lead.status = 'enriched';

return [{ json: lead }];"""


def serper_json_body(q_expr: str, num: int) -> str:
    # q_expr is JS expression for q without outer quotes, e.g. $('Normalize Variables').first().json.country
    inner = (
        f"'site:members.sca.coffee OR site:sca.coffee/find-a-member ' + "
        f"$('Normalize Variables').first().json.country + ' coffee importer exporter broker'"
    )
    if q_expr == "sca":
        q_js = inner
    elif q_expr == "nca":
        q_js = (
            "'site:ncausa.org member directory ' + "
            "$('Normalize Variables').first().json.country + ' coffee buyer seller importer exporter'"
        )
    elif q_expr == "gafta":
        q_js = (
            "'site:gafta.com approved members ' + "
            "$('Normalize Variables').first().json.country + ' grain cereal broker freight forwarder'"
        )
    elif q_expr == "email":
        q_js = (
            "'\"' + $json.company + '\" email contact ' + $('Normalize Variables').first().json.country"
        )
    elif q_expr == "social":
        q_js = (
            "'\"' + $json.company + '\" site:linkedin.com/company OR site:twitter.com OR site:x.com OR site:wa.me ' + "
            "$('Normalize Variables').first().json.country"
        )
    else:
        raise ValueError(q_expr)
    return (
        "={{ JSON.stringify({ q: "
        + q_js
        + ", gl: 'us', hl: 'en', num: "
        + str(num)
        + " }) }}"
    )


def http_serper_params(q_key: str, num: int) -> dict:
    return {
        "method": "POST",
        "url": "https://google.serper.dev/search",
        "authentication": "none",
        "sendHeaders": True,
        "headerParameters": {
            "parameters": [
                {
                    "name": "X-API-KEY",
                    "value": "={{ $('Normalize Variables').first().json.serperKey }}",
                },
                {"name": "Content-Type", "value": "application/json"},
            ]
        },
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": serper_json_body(q_key, num),
        "options": {},
    }


def main() -> None:
    data = json.loads(WF_PATH.read_text(encoding="utf-8"))
    nodes = data["nodes"]

    # Remove old Set Variables node
    nodes = [n for n in nodes if n.get("id") != "d1b1ec3e-967d-49d2-b2f6-48d5a051d189"]

    # Replace Normalize Payload with Code node Normalize Variables (reuse id for stable imports)
    for n in nodes:
        if n.get("id") == "2511bbc1-9a42-4e2e-915f-6294b52053f7":
            n["name"] = "Normalize Variables"
            n["type"] = "n8n-nodes-base.code"
            n["typeVersion"] = 2
            n["parameters"] = {"jsCode": NORMALIZE_JS}
            break

    name_map = {
        "Serper – SCA Directory": "sca",
        "Serper – NCA Directory": "nca",
        "Serper – GAFTA Directory": "gafta",
        "Serper – Email Search": "email",
        "Serper – Social & Phone Search": "social",
    }
    for n in nodes:
        key = name_map.get(n.get("name"))
        if key:
            n["parameters"] = http_serper_params(key, 10 if key in ("sca", "nca", "gafta") else 5)

    for n in nodes:
        if n.get("name") == "Code – Parse Leads":
            n["parameters"] = {"jsCode": PARSE_LEADS_JS}
        if n.get("name") == "Code – Extract Contacts":
            n["parameters"] = {"jsCode": EXTRACT_CONTACTS_JS}
        if n.get("name") == "Code – PDF Contacts":
            n["parameters"] = {"jsCode": PDF_CONTACTS_JS}
        if n.get("name") == "Split In Batches":
            n["parameters"] = {"batchSize": 1, "options": {}}
        if n.get("name") == "Respond to Webhook":
            n["parameters"]["responseBody"] = (
                "={\n"
                '  "success": true,\n'
                '  "country": "{{ $(\'Normalize Variables\').first().json.country }}",\n'
                "  \"categories\": {{ JSON.stringify($('Normalize Variables').first().json.categories) }},\n"
                '  "triggeredAt": "{{ $(\'Normalize Variables\').first().json.triggeredAt }}",\n'
                '  "message": "Pipeline complete. Leads written to Google Sheet."\n'
                "}"
            )
        if n.get("name") == "Google Sheets – Append Row":
            cols = n["parameters"]["columns"]
            cols["value"]["Leads_Id"] = "={{ $json.leadsId }}"
            # Prepend Leads_Id to schema
            lead_schema = {
                "id": "Leads_Id",
                "displayName": "Leads_Id",
                "required": False,
                "defaultMatch": False,
                "display": True,
                "type": "string",
                "canBeUsedToMatch": True,
            }
            cols["schema"] = [lead_schema] + cols["schema"]

    # New nodes: IF, PDF.co (https://api.pdf.co/v1/pdf/convert/to/text), Code PDF
    nid_if = str(uuid.uuid4())
    nid_pdfco = str(uuid.uuid4())
    nid_pdf = str(uuid.uuid4())

    nodes.extend(
        [
            {
                "parameters": {
                    "conditions": {
                        "options": {
                            "caseSensitive": True,
                            "leftValue": "",
                            "typeValidation": "strict",
                        },
                        "conditions": [
                            {
                                "id": str(uuid.uuid4()),
                                "leftValue": "={{ ($json.sourceUrl || '').toLowerCase() }}",
                                "rightValue": ".pdf",
                                "operator": {"type": "string", "operation": "endsWith"},
                            }
                        ],
                        "combinator": "and",
                    },
                    "options": {},
                },
                "id": nid_if,
                "name": "IF – Source Is PDF",
                "type": "n8n-nodes-base.if",
                "typeVersion": 2,
                "position": [-1184, 976],
            },
            {
                "parameters": {
                    "method": "POST",
                    "url": "https://api.pdf.co/v1/pdf/convert/to/text",
                    "authentication": "none",
                    "sendHeaders": True,
                    "headerParameters": {
                        "parameters": [
                            {"name": "Content-Type", "value": "application/json"},
                            {
                                "name": "x-api-key",
                                "value": "={{ $('Normalize Variables').first().json.pdfCoApiKey }}",
                            },
                        ]
                    },
                    "sendBody": True,
                    "specifyBody": "json",
                    "jsonBody": "={{ JSON.stringify({ url: $json.sourceUrl, inline: true, async: false, lang: 'eng' }) }}",
                    "options": {},
                },
                "id": nid_pdfco,
                "name": "PDF.co – PDF to Text",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4,
                "position": [-960, 800],
            },
            {
                "parameters": {"jsCode": PDF_CONTACTS_JS},
                "id": nid_pdf,
                "name": "Code – PDF Contacts",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "position": [-512, 800],
            },
        ]
    )

    data["nodes"] = nodes

    # Connections
    con = data["connections"]
    con["Webhook"] = {
        "main": [[{"node": "Normalize Variables", "type": "main", "index": 0}]]
    }
    del con["Normalize Payload"]
    con["Normalize Variables"] = {
        "main": [
            [
                {"node": "Serper – SCA Directory", "type": "main", "index": 0},
                {"node": "Serper – NCA Directory", "type": "main", "index": 0},
                {"node": "Serper – GAFTA Directory", "type": "main", "index": 0},
            ]
        ]
    }
    del con["Set Variables"]

    con["Split In Batches"] = {
        "main": [
            [{"node": "IF – Source Is PDF", "type": "main", "index": 0}],
            [{"node": "Respond to Webhook", "type": "main", "index": 0}],
        ]
    }

    con["IF – Source Is PDF"] = {
        "main": [
            [{"node": "PDF.co – PDF to Text", "type": "main", "index": 0}],
            [
                {"node": "Serper – Email Search", "type": "main", "index": 0},
                {"node": "Serper – Social & Phone Search", "type": "main", "index": 0},
            ],
        ]
    }
    con["PDF.co – PDF to Text"] = {
        "main": [[{"node": "Code – PDF Contacts", "type": "main", "index": 0}]]
    }
    con["Code – PDF Contacts"] = {
        "main": [[{"node": "Google Sheets – Append Row", "type": "main", "index": 0}]]
    }

    con["Serper – Email Search"] = {
        "main": [[{"node": "Code – Extract Contacts", "type": "main", "index": 0}]]
    }
    con["Serper – Social & Phone Search"] = {
        "main": [[{"node": "Code – Extract Contacts", "type": "main", "index": 1}]]
    }

    if "pinData" in data:
        data["pinData"] = {}

    WF_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Wrote", WF_PATH)


if __name__ == "__main__":
    main()
