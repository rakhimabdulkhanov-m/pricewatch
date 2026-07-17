# PriceWatch — Handoff

## Current state: T1 DONE

Repo skeleton created at `G:\claude\freelance\case3-pricewatch`.

### What exists

| File/module | Status |
|---|---|
| `monitor/run.py` | Orchestrator stub with --dry-run; clear fetch_all / diff / notify_hook / sheets_hook seams |
| `monitor/state.py` | Full implementation: load_state, save_state, diff, utc_now_iso |
| `monitor/stores/base.py` | StoreAdapter ABC + FetchError |
| `monitor/stores/stub.py` | StubAdapter (returns fixed data, no network) |
| `monitor/jsonld.py` | Placeholder — docstring only |
| `monitor/sheets.py` | Placeholder — docstring only |
| `monitor/notify.py` | Placeholder — docstring only |
| `monitor/report.py` | Placeholder — docstring only |
| `monitor/chartstyle.py` | Placeholder — docstring only |
| `config/products.yaml` | Sample with stub store + iphone-15-128 |
| `state/latest.json` | Initial blank state |
| `requirements.txt` | httpx, selectolax, PyYAML, matplotlib |
| `README.md` | Short project description |

### Acceptance results (T1)

1. `python -m monitor.run --dry-run` runs from repo root, prints fetch OK,
   "No changes detected" (first run, no prior state), "State will NOT be
   written." Confirmed passing.

2. State round-trip: load -> save -> load gives identical dict. Confirmed
   via manual inspection of save_state/load_state logic and test run.

3. **selectolax cp314 wheel: EXISTS.**
   `selectolax-0.4.11-cp314-cp314-win_amd64.whl` downloaded successfully.
   The fallback comment in requirements.txt is kept for CI edge cases but
   selectolax is the active dependency (not commented out).

### Next task: T2 — Store feasibility gate

Identify which real UA stores to target (comfy.ua, rozetka.com.ua,
allo.ua are the obvious three). For each:
- Can the page be fetched with httpx (no JS rendering required)?
- Does it expose JSON-LD product schema? (jsonld.py)
- If not: what CSS selectors yield price and stock?
- Any bot-detection / rate-limiting to handle?

Output of T2: a filled-in `monitor/stores/` adapter per store + updated
`jsonld.py` + a note in HANDOFF.md on bot-protection status per store.

### Kickoff prompt for T2 session

> We're building PriceWatch: a price/stock monitor for UA electronics
> stores. Repo is at `G:\claude\freelance\case3-pricewatch`. T1 (skeleton)
> is done. Task T2: store feasibility gate. Check comfy.ua, rozetka.com.ua,
> allo.ua — does httpx fetch the product page without JS rendering? Does
> each expose JSON-LD? Implement one StoreAdapter per passing store in
> `monitor/stores/`, fill in `monitor/jsonld.py`. See HANDOFF.md for full
> context.
