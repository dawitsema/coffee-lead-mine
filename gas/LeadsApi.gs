/**
 * Bind to your Leads spreadsheet (Extensions → Apps Script).
 *
 * Script properties (optional overrides):
 *   LEADS_API_TOKEN  — required secret for JSONP calls
 *   SHEET1_NAME      — default "Sheet1" (ingestion / n8n: Leads_Id, Status, …)
 *   SHEET2_NAME      — default "Sheet2" (pipeline CRM columns)
 *
 * Sheet1 row 1: Leads_Id, Company, Country, Sector, Role, Email, Phone, LinkedIn, Twitter/X,
 *              WhatsApp, Source, Source URL, Status, Enriched At
 *
 * Sheet2 row 1: Leads_Id, Company, Country, Sector, Role, Email, Contacted, Response,
 *              Interest Level, Last contact date, Deal Status
 */

function getToken_() {
  var t = PropertiesService.getScriptProperties().getProperty('LEADS_API_TOKEN');
  if (!t) throw new Error('Set Script property LEADS_API_TOKEN');
  return t;
}

function getProp_(key, defaultValue) {
  var v = PropertiesService.getScriptProperties().getProperty(key);
  return v && String(v).trim() ? String(v).trim() : defaultValue;
}

function getSpreadsheet_() {
  return SpreadsheetApp.getActiveSpreadsheet();
}

function getSheet1_() {
  return getSpreadsheet_().getSheetByName(getProp_('SHEET1_NAME', 'Sheet1'));
}

function getSheet2_() {
  return getSpreadsheet_().getSheetByName(getProp_('SHEET2_NAME', 'Sheet2'));
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

function rowsToObjects_(sheet) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
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

function listLeads_() {
  var sh = getSheet1_();
  if (!sh) throw new Error('Sheet1 not found (rename tab or set SHEET1_NAME)');
  return rowsToObjects_(sh);
}

function listPipeline_() {
  var sh = getSheet2_();
  if (!sh) throw new Error('Sheet2 not found (rename tab or set SHEET2_NAME)');
  return rowsToObjects_(sh);
}

/** Resolve primary id column: Leads_Id (preferred) or legacy LeadId */
function idColumn_(map) {
  if (map['Leads_Id']) return map['Leads_Id'];
  if (map['LeadId']) return map['LeadId'];
  return null;
}

function updateStatus_(leadsId, status) {
  if (!leadsId) throw new Error('leadsId required');
  var sheet = getSheet1_();
  if (!sheet) throw new Error('Sheet1 not found');
  var map = headerIndexMap_(sheet);
  var idCol = idColumn_(map);
  var stCol = map['Status'];
  if (!idCol) throw new Error('Leads_Id column missing in Sheet1 row 1');
  if (!stCol) throw new Error('Status column missing in Sheet1 row 1');
  var lastRow = sheet.getLastRow();
  var range = sheet.getRange(2, idCol, Math.max(2, lastRow), idCol).getValues();
  for (var i = 0; i < range.length; i++) {
    if (String(range[i][0]) === String(leadsId)) {
      sheet.getRange(i + 2, stCol).setValue(status);
      return { updated: true, row: i + 2, sheet: 'Sheet1' };
    }
  }
  throw new Error('Leads_Id not found on Sheet1: ' + leadsId);
}

/**
 * Update CRM fields on Sheet2 for one Leads_Id. Only non-empty params overwrite cells.
 * Headers must match: Contacted, Response, Interest Level, Last contact date, Deal Status
 */
function updatePipeline_(params) {
  var leadsId = params.leadsId || params.leadId;
  if (!leadsId) throw new Error('leadsId required');
  var sheet = getSheet2_();
  if (!sheet) throw new Error('Sheet2 not found');
  var map = headerIndexMap_(sheet);
  var idCol = idColumn_(map);
  if (!idCol) throw new Error('Leads_Id column missing in Sheet2 row 1');

  var lastRow = sheet.getLastRow();
  var range = sheet.getRange(2, idCol, Math.max(2, lastRow), idCol).getValues();
  var rowIndex = -1;
  for (var i = 0; i < range.length; i++) {
    if (String(range[i][0]) === String(leadsId)) {
      rowIndex = i + 2;
      break;
    }
  }
  if (rowIndex < 0) throw new Error('Leads_Id not found on Sheet2: ' + leadsId);

  var fieldMap = {
    contacted: 'Contacted',
    response: 'Response',
    interestLevel: 'Interest Level',
    lastContactDate: 'Last contact date',
    dealStatus: 'Deal Status',
    company: 'Company',
    country: 'Country',
    sector: 'Sector',
    role: 'Role',
    email: 'Email',
  };
  var updated = [];
  for (var jsKey in fieldMap) {
    if (!Object.prototype.hasOwnProperty.call(fieldMap, jsKey)) continue;
    if (!Object.prototype.hasOwnProperty.call(params, jsKey)) continue;
    var val = params[jsKey];
    if (val === undefined || val === null || String(val) === '') continue;
    var colName = fieldMap[jsKey];
    var col = map[colName];
    if (!col) continue;
    sheet.getRange(rowIndex, col).setValue(val);
    updated.push(colName);
  }
  return { updated: true, row: rowIndex, fields: updated };
}

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
    if (action === 'listPipeline') {
      return jsonpOut_(callback, { ok: true, pipeline: listPipeline_() });
    }
    if (action === 'updateStatus') {
      var lid = p.leadsId || p.leadId;
      var res = updateStatus_(lid, p.status);
      return jsonpOut_(callback, { ok: true, result: res });
    }
    if (action === 'updatePipeline') {
      var res2 = updatePipeline_(p);
      return jsonpOut_(callback, { ok: true, result: res2 });
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
