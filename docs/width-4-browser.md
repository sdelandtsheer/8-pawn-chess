# Width 4 Browser Milestone

This milestone replaces the browser heuristic engine with exact tablebase lookup for the width 4 game.

Generated paste-ready file:

```text
browser/wix_width4_tablebase.html
```

Source files:

```text
browser/tablebase_core.js
browser/wix_width4_template.html
browser/build_wix_html.py
browser/verify_width4_tablebase.js
```

The generated HTML keeps the existing interface structure and styling, but changes the engine panel to show:

- tablebase load state / row count
- hit/miss and outcome for the side to move
- DTM

## Local Test Flow

1. Host the repo locally:

```powershell
py -m http.server 8000
```

2. In `browser/wix_width4_tablebase.html`, set:

```javascript
const TABLEBASE_URL = "http://localhost:8000/dist/w4/tablebase.jsonl.gz";
```

3. Open `browser/wix_width4_tablebase.html` in a browser.
4. Start the game once the button is enabled.
5. If playing Black, the tablebase should immediately play `b2b4` for White.

The welcome modal is intentionally minimal: only `Blancs`, `Noirs`, and `Commencer`.

## Wix Flow

For Wix deployment, host or upload the width 4 tablebase file:

```text
dist/w4/tablebase.jsonl.gz
```

Then edit this line in `browser/wix_width4_tablebase.html` before pasting it into Wix:

```javascript
const TABLEBASE_URL = "";
```

Set it to the public URL of the hosted tablebase:

```javascript
const TABLEBASE_URL = "https://example.com/tablebase.jsonl.gz";
```

The browser can load either plain JSONL or gzip JSONL. If the server does not send gzip as decoded text, modern browsers use `DecompressionStream` to decompress it locally.

## Verification

Default browser-core smoke test:

```powershell
node tests/browser_core_smoke.js
```

End-to-end verification against the generated width 4 tablebase:

```powershell
node browser/verify_width4_tablebase.js
```

Expected output:

```json
{
  "rows": 1033490,
  "initialKey": "f0000000000000000000000000f00",
  "outcome": 1,
  "dtm": 21,
  "bestMove": "b2b4",
  "childOutcome": -1,
  "childDtm": 20
}
```
