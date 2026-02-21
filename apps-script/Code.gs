/**
 * Google Apps Script: Zendesk Ticket Export for Labeling
 * Exports tickets to Sheets for manual labeling / active learning.
 * Run from Script Editor or trigger on schedule.
 */

const ZENDESK_SUBDOMAIN = 'YOUR_SUBDOMAIN';  // e.g. mycompany
const ZENDESK_EMAIL = 'YOUR_EMAIL@domain.com';
const ZENDESK_API_TOKEN = 'YOUR_API_TOKEN';
const SPREADSHEET_ID = 'YOUR_SHEET_ID';  // Create a Sheet, copy ID from URL
const SHEET_NAME = 'Tickets';

/**
 * One-time setup: create sheet with headers.
 */
function setupSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) sheet = ss.insertSheet(SHEET_NAME);
  sheet.clear();
  sheet.getRange(1, 1, 1, 6).setValues([['ticket_id', 'subject', 'first_comment', 'channel', 'created_at', 'label (edit)']]);
  sheet.getRange(1, 1, 1, 6).setFontWeight('bold');
}

/**
 * Fetch recent tickets from Zendesk and append to sheet.
 * Uses Incremental Export or list tickets.
 */
function exportTicketsForLabeling() {
  const auth = Utilities.base64Encode(ZENDESK_EMAIL + '/token:' + ZENDESK_API_TOKEN);
  const url = `https://${ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets.json?sort_by=created_at&sort_order=desc&per_page=100`;
  
  const options = {
    method: 'get',
    headers: { Authorization: 'Basic ' + auth },
    muteHttpExceptions: true
  };

  const response = UrlFetchApp.fetch(url, options);
  if (response.getResponseCode() !== 200) {
    Logger.log('Zendesk API error: ' + response.getContentText());
    return;
  }

  const data = JSON.parse(response.getContentText());
  const tickets = data.tickets || [];
  const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    setupSheet();
    sheet = ss.getSheetByName(SHEET_NAME);
  }

  const rows = tickets.slice(0, 100).map(t => [
    t.id,
    t.subject || '',
    (t.description || '').substring(0, 500),
    t.via?.channel || '',
    t.created_at || '',
    ''
  ]);

  if (rows.length) {
    const lastRow = sheet.getLastRow();
    sheet.getRange(lastRow + 1, 1, lastRow + rows.length, 6).setValues(rows);
  }

  Logger.log('Exported ' + rows.length + ' tickets');
}
