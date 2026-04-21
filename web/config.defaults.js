/** Safe defaults — override by adding optional `config.js` (see config.sample.js). */
window.LEADS_CONFIG = Object.assign(
  {
    proxyTriggerUrl: '',
    gasBaseUrl: '',
    gasToken: '',
  },
  window.LEADS_CONFIG || {},
);
