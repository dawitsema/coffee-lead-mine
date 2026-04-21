/**
 * Vercel serverless route: deploy this repo with root = project folder containing /api.
 * Env: N8N_WEBHOOK_URL = full POST URL of your n8n webhook (kept server-side).
 */
module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') {
    return res.status(204).end();
  }
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Use POST' });
  }
  const target = process.env.N8N_WEBHOOK_URL;
  if (!target) {
    return res.status(500).json({ error: 'N8N_WEBHOOK_URL is not set' });
  }
  try {
    const body = typeof req.body === 'string' ? req.body : JSON.stringify(req.body || {});
    const r = await fetch(target, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    const text = await r.text();
    let out = text;
    try {
      out = JSON.stringify(JSON.parse(text));
    } catch {
      /* keep text */
    }
    res.status(r.status);
    res.setHeader('Content-Type', 'application/json');
    return res.send(out);
  } catch (e) {
    return res.status(502).json({ error: String(e && e.message ? e.message : e) });
  }
};
