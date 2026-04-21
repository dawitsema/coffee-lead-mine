/**
 * Bind this script to your Leads spreadsheet (Extensions → Apps Script).
 *
 * 1. File → Project settings → Script properties → Add row:
 *    LEADS_API_TOKEN = (long random secret)
 * 2. Deploy → New deployment → Type: Web app
 *    Execute as: Me
 *    Who has access: Anyone (JSONP is used from static sites; token still required)
 * 3. Copy the Web app URL into your dashboard CONFIG.gasBaseUrl (no query string).
 *
 * Sheet row 1 headers must include: LeadId, Company, Country, Sector, Role, Email, Phone,
 * LinkedIn, Twitter/X, WhatsApp, Source, Source URL, Status, Enriched At
 * (match your n8n Google Sheets column names; order can vary).
 */

function getToken_() {
  var t = PropertiesService.getScriptProperties().getProperty('LEADS_API_TOKEN');
  if (!t) throw new Error('Set Script property LEADS_API_TOKEN');
  return t;
}

function getSheet_() {
  return SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
}

function headerIndexMap_(sheet) {
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var map = {};
  for (var c = 0; c < headers.length; c++) {
    var h = String(headers[c] || '').trim();
    if (h) map[h] = c + 1;
  }
  return map;
}

function listLeads_() {
  var sheet = getSheet_();
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var map = headerIndexMap_(sheet);
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var data = sheet.getRange(2, 1, lastRow, sheet.getLastColumn()).getValues();
  var leads = [];
  for (var r = 0; r < data.length; r++) {
    var row = data[r];
    var obj = {};
    for (var c = 0; c < headers.length; c++) {
      var key = String(headers[c] || '').trim();
      if (!key) continue;
      var v = row[c];
      obj[key] = v === null || v === undefined ? '' : String(v);
    }
    leads.push(obj);
  }
  return leads;
}

function updateStatus_(leadId, status) {
  if (!leadId) throw new Error('leadId required');
  var sheet = getSheet_();
  var map = headerIndexMap_(sheet);
  var idCol = map['LeadId'];
  var stCol = map['Status'];
  if (!idCol) throw new Error('LeadId column missing in row 1');
  if (!stCol) throw new Error('Status column missing in row 1');
  var lastRow = sheet.getLastRow();
  var range = sheet.getRange(2, idCol, Math.max(2, lastRow), idCol).getValues();
  for (var i = 0; i < range.length; i++) {
    if (String(range[i][0]) === String(leadId)) {
      sheet.getRange(i + 2, stCol).setValue(status);
      return { updated: true, row: i + 2 };
    }
  }
  throw new Error('LeadId not found: ' + leadId);
}

/**
 * JSONP for browser use (no CORS headers available on Apps Script TextOutput).
 * Request: .../exec?action=list&token=...&callback=myCb
 * Response body: myCb({"ok":true,"leads":[...]});
 */
function doGet(e) {
  var p = e && e.parameter ? e.parameter : {};
  var callback = p.callback || 'leadsCallback';
  try {
    var token = getToken_();
    if (String(p.token || '') !== String(token)) {
      return jsonpOut_(callback, { ok: false, error: 'unauthorized' });
    }
    var action = String(p.action || '');
    if (action === 'list') {
      return jsonpOut_(callback, { ok: true, leads: listLeads_() });
    }
    if (action === 'updateStatus') {
      var res = updateStatus_(p.leadId, p.status);
      return jsonpOut_(callback, { ok: true, result: res });
    }
    return jsonpOut_(callback, { ok: false, error: 'unknown_action' });
  } catch (err) {
    return jsonpOut_(callback, { ok: false, error: String(err && err.message ? err.message : err) });
  }
}

function jsonpOut_(callback, obj) {
  var safeCb = /^[a-zA-Z_$][a-zA-Z0-9_$]*$/.test(callback) ? callback : 'leadsCallback';
  var body = safeCb + '(' + JSON.stringify(obj) + ');';
  return ContentService.createTextOutput(body).setMimeType(ContentService.MimeType.JAVASCRIPT);
}
