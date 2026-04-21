const cors = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: cors };
  }
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers: cors, body: JSON.stringify({ error: 'Use POST' }) };
  }
  const target = process.env.N8N_WEBHOOK_URL;
  if (!target) {
    return {
      statusCode: 500,
      headers: { ...cors, 'Content-Type': 'application/json' },
      body: JSON.stringify({ error: 'N8N_WEBHOOK_URL is not set in Netlify environment' }),
    };
  }
  try {
    const res = await fetch(target, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: event.body || '{}',
    });
    const text = await res.text();
    let body = text;
    try {
      body = JSON.stringify(JSON.parse(text));
    } catch {
      /* keep raw */
    }
    return {
      statusCode: res.status,
      headers: { ...cors, 'Content-Type': 'application/json' },
      body,
    };
  } catch (e) {
    return {
      statusCode: 502,
      headers: { ...cors, 'Content-Type': 'application/json' },
      body: JSON.stringify({ error: String(e && e.message ? e.message : e) }),
    };
  }
};
