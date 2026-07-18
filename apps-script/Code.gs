// Google Apps Script web app — PriceWatch price history spreadsheet.
//
// Spreadsheet: "PriceWatch — price history"
// Required tabs (exact names): history, current
//
// DEPLOY INSTRUCTIONS:
//   1. Create a Google Sheet named "PriceWatch — price history".
//      Inside the sheet add two tabs: rename "Sheet1" to "history",
//      then click "+" and name the second tab "current".
//   2. Extensions → Apps Script → delete placeholder code → paste this file → Save (Ctrl+S).
//   3. Deploy → New deployment → click the gear icon → Web app.
//      Execute as: Me | Who has access: Anyone → Deploy.
//   4. Click "Authorise access" and allow the requested Google permissions.
//   5. Copy the /exec URL — set it as SHEETS_WEBHOOK_URL in your .env file.
//
// POST body : {"rows": [[checked_at_utc, store, product_id, name, price_uah, in_stock], ...]}
// POST response: {"ok": true, "appended": N}  |  {"ok": false, "error": "..."}
//
// GET  param : days=N (default 30)
// GET  response: [{checked_at_utc, store, product_id, name, price_uah, in_stock}, ...]

var HISTORY_TAB = 'history';
var CURRENT_TAB = 'current';
var CURRENT_HEADER = ['product_id', 'name', 'store', 'price_uah',
                      'prev_price_uah', 'delta_pct', 'in_stock', 'updated_at_utc'];
var HIST_COLS = 6; // checked_at_utc | store | product_id | name | price_uah | in_stock

function doPost(e) {
  try {
    var payload = JSON.parse(e.postData.contents);
    var newRows = payload.rows || [];
    if (!newRows.length) {
      return _json({ok: true, appended: 0});
    }

    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var hist = ss.getSheetByName(HISTORY_TAB);

    // Batch-append to history (one setValues call, not appendRow loop).
    var startRow = hist.getLastRow() + 1;
    hist.getRange(startRow, 1, newRows.length, newRows[0].length).setValues(newRows);

    // Rebuild current tab from entire history.
    _rebuildCurrent(ss, hist);

    return _json({ok: true, appended: newRows.length});
  } catch (err) {
    return _json({ok: false, error: String(err)});
  }
}

function doGet(e) {
  try {
    var days = parseInt((e.parameter && e.parameter.days) || '30', 10);
    var cutoff = new Date(Date.now() - days * 86400 * 1000);

    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var hist = ss.getSheetByName(HISTORY_TAB);
    var all = _readHistory(hist);

    var result = [];
    for (var i = 0; i < all.length; i++) {
      var row = all[i];
      if (new Date(String(row[0])) >= cutoff) {
        result.push({
          checked_at_utc: String(row[0]),
          store:          String(row[1]),
          product_id:     String(row[2]),
          name:           String(row[3]),
          price_uah:      row[4],
          in_stock:       row[5],
        });
      }
    }
    return _json(result);
  } catch (err) {
    return _json({ok: false, error: String(err)});
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function _readHistory(hist) {
  var lastRow = hist.getLastRow();
  if (lastRow < 1) return [];
  return hist.getRange(1, 1, lastRow, HIST_COLS).getValues().filter(function(r) {
    return r[0] !== '';
  });
}

function _rebuildCurrent(ss, hist) {
  var all = _readHistory(hist);

  // Group rows by "product_id|store" key.
  var map = {};
  for (var i = 0; i < all.length; i++) {
    var key = String(all[i][2]) + '|' + String(all[i][1]);
    if (!map[key]) map[key] = [];
    map[key].push(all[i]);
  }

  // Sort each group ascending by ISO timestamp (lexicographic == chronological).
  for (var k in map) {
    map[k].sort(function(a, b) { return String(a[0]) < String(b[0]) ? -1 : 1; });
  }

  // Build one output row per (product_id, store) pair.
  var currentRows = [];
  for (var k in map) {
    var rows = map[k];
    var latest = rows[rows.length - 1];
    var curPrice = latest[4];

    // Previous DISTINCT price, scanning backward from second-to-last row.
    var prevPrice = '';
    for (var j = rows.length - 2; j >= 0; j--) {
      if (rows[j][4] !== curPrice) { prevPrice = rows[j][4]; break; }
    }

    // delta_pct = (price - prev) / prev * 100, 1 decimal; blank when no prev.
    var delta = '';
    if (prevPrice !== '') {
      delta = Math.round((curPrice - prevPrice) / prevPrice * 1000) / 10;
    }

    currentRows.push([
      String(latest[2]),  // product_id
      String(latest[3]),  // name
      String(latest[1]),  // store
      curPrice,           // price_uah
      prevPrice,          // prev_price_uah ('' = blank)
      delta,              // delta_pct      ('' = blank)
      latest[5],          // in_stock
      String(latest[0]),  // updated_at_utc
    ]);
  }

  // Sort by product_id then store.
  currentRows.sort(function(a, b) {
    if (a[0] !== b[0]) return a[0] < b[0] ? -1 : 1;
    return a[2] < b[2] ? -1 : 1;
  });

  // Overwrite current tab: header (bold) + data.
  var cur = ss.getSheetByName(CURRENT_TAB);
  cur.clearContents();
  var headerRange = cur.getRange(1, 1, 1, CURRENT_HEADER.length);
  headerRange.setValues([CURRENT_HEADER]);
  headerRange.setFontWeight('bold');
  if (currentRows.length > 0) {
    cur.getRange(2, 1, currentRows.length, CURRENT_HEADER.length).setValues(currentRows);
  }
}

function _json(data) {
  return ContentService
    .createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
