# Google Sheets webhook — deploy walkthrough

## 1. Create the spreadsheet

1. Go to https://sheets.google.com and create a new spreadsheet.
2. Name it exactly: **PriceWatch — price history**
3. Rename the default tab from "Sheet1" to **history** (double-click the tab name).
4. Click the **+** button to add a second tab and name it **current**.

## 2. Paste the Apps Script

1. In the spreadsheet: **Extensions → Apps Script**.
2. Delete all placeholder code in the editor.
3. Copy the contents of `apps-script/Code.gs` and paste into the editor.
4. Press **Ctrl+S** (or the save icon) and name the project anything (e.g. "PriceWatch").

## 3. Deploy as a web app

1. Click **Deploy → New deployment**.
2. Click the gear icon next to "Select type" and choose **Web app**.
3. Set **Execute as: Me** (your Google account).
4. Set **Who has access: Anyone**.
5. Click **Deploy**.
6. Click **Authorise access** and follow the Google permissions prompt.
7. Copy the URL that ends in `/exec` — this is your webhook URL.

## 4. Add the URL to your project

Open `.env` in the project root and fill in:

```
SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec
```

## 5. Post-deploy verification

### Test POST (append 2 rows and rebuild current tab)

```bash
curl -s -L -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "rows": [
      ["2026-07-17T10:00:00Z", "comfy", "iphone-15-128", "iPhone 15 128GB", 32999, true],
      ["2026-07-17T11:00:00Z", "comfy", "iphone-15-128", "iPhone 15 128GB", 31499, true]
    ]
  }' \
  "$SHEETS_WEBHOOK_URL"
```

Expected response: `{"ok":true,"appended":2}`

After this call:
- **history** tab should have 2 data rows.
- **current** tab should have a bold header row + 1 data row with `delta_pct = -4.5`
  (price dropped from 32999 to 31499).

### Test GET (read back last 30 days)

```bash
curl -s -L "$SHEETS_WEBHOOK_URL?days=30"
```

Expected response: JSON array with 2 objects, each having keys
`checked_at_utc`, `store`, `product_id`, `name`, `price_uah`, `in_stock`.

### Python verification (alternative to curl)

```python
import httpx, os

url = os.environ["SHEETS_WEBHOOK_URL"]

# POST
r = httpx.post(url, json={"rows": [
    ["2026-07-17T10:00:00Z", "comfy", "iphone-15-128", "iPhone 15 128GB", 32999, True],
    ["2026-07-17T11:00:00Z", "comfy", "iphone-15-128", "iPhone 15 128GB", 31499, True],
]}, follow_redirects=True, timeout=30)
print(r.json())  # {"ok": True, "appended": 2}

# GET
r = httpx.get(url, params={"days": 30}, follow_redirects=True, timeout=30)
print(r.json())  # list of 2 dicts
```

## Notes

- The `-L` flag in curl (or `follow_redirects=True` in httpx) is required — Apps Script
  redirects POST requests to `script.googleusercontent.com` before executing.
- Re-deploying after code changes requires **Deploy → Manage deployments → Edit → New version**.
  The `/exec` URL stays the same.
- If you see a Google login page in the response, the "Who has access" setting was not
  set to "Anyone" — redeploy with the correct setting.
