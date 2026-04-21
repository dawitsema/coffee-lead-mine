/**
 * Copy to web/config.js (gitignored) and fill values.
 * Loads after config.defaults.js — you can assign only the keys you need.
 */
window.LEADS_CONFIG = Object.assign(window.LEADS_CONFIG || {}, {
  /** Netlify: /.netlify/functions/trigger-leads  |  Vercel: /api/trigger-leads */
  proxyTriggerUrl: 'https://YOUR_SITE.netlify.app/.netlify/functions/trigger-leads',
  /** Google Apps Script Web app URL (ends with /exec) */
  gasBaseUrl: 'https://script.google.com/macros/s/YOUR_DEPLOYMENT/exec',
  /** Same value as Script property LEADS_API_TOKEN */
  gasToken: 'YOUR_LONG_RANDOM_TOKEN',
});
