/**
 * Copy to web/config.js (gitignored) and fill values.
 * Loads after config.defaults.js — you can assign only the keys you need.
 */
window.LEADS_CONFIG = Object.assign(window.LEADS_CONFIG || {}, {
  proxyTriggerUrl:
    "https://cofferleadminer.netlify.app/.netlify/functions/trigger-leads",
  /** Google Apps Script Web app URL (ends with /exec) */
  gasBaseUrl:
    "https://script.google.com/macros/s/AKfycbzb_t3h2Xy2-0TNAVRxhWhaDGtWG3nhCcR_HFeXhYU7Qmc5sLh6O9rXY8jPZddG0-ML/exec",
  /** Same value as Script property LEADS_API_TOKEN */
  gasToken: "9a3c6b2f7f0e4c9dbd4c8b2ad7e1f3a16783fjie483",
});
