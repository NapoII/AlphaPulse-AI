# AlphaPulse‑AI — Market Brief & AI Signals (Flask)

AlphaPulse‑AI is a compact Flask app that crawls Yahoo Finance headlines for selected tickers, fetches basic indicators via yfinance, and asks OpenAI to produce a grounded Daily Brief in Markdown with numbered citations to real sources. It also returns a JSON block of Buy/Sell signals with short reasons. The UI renders the Markdown, shows signal buttons linking to Yahoo Finance, includes a live “time since last update” counter, and provides a streaming progress overlay when you run a new analysis.

Why it stands out:
- Grounded Daily Brief with inline citations [n] mapped to a numbered Sources list
- Clean, dark “glass” UI with a centered header and a live “last updated” counter
- One‑click Run with a real‑time progress overlay (SSE) and step‑by‑step logs
- Login‑protected dashboard and API key setup/validation page
- Results are persisted and shown until you choose to run again

## Features

- News: Yahoo Finance RSS + lightweight search, deduplicated per ticker
- Indicators: yfinance for price/prev_close/change %, market cap, PE, etc.
- LLM: OpenAI chat completions produce:
  - Markdown report containing:
    - Daily Brief (4–7 sentences) with inline numeric citations [1], [2], …
    - Optional Key Indicators section (only if any values exist)
    - Per‑ticker insights referencing news/indicators with citations
    - Numbered Sources list (1..N) from the provided news URLs
  - JSON object: { "signals": [{ ticker, name, action, reason }...] }
    - Reasons are concise and tie back to the cited sources (e.g., mentions [2])
- UI/UX:
  - Live count‑up badge for “time since last update” (seconds → minutes → hours → days)
  - “Run now” starts a streaming run with a progress bar and live logs
  - Signal buttons open Yahoo Finance pages for the recommended tickers
  - News list with ticker badges linking to Yahoo quote pages

## Quickstart (Windows PowerShell)

Requirements: Python 3.10+ recommended.

1) Create and activate a virtual environment

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
```

2) Install dependencies

```powershell
pip install -r requirements.txt
```

3) Optional: set environment variables (you can also enter the OpenAI key in the app)

```powershell
$env:SECRET_KEY = "change-me"            # Flask session secret
$env:APP_USERNAME = "admin"              # Demo login (override for prod)
$env:APP_PASSWORD = "admin123"
# LLM settings
$env:OPENAI_MODEL = "gpt-4o-mini"
$env:OPENAI_API_BASE = "https://api.openai.com/v1"
# Don’t auto-run on startup (default behavior)
$env:RUN_ON_STARTUP = "0"
```

4) Run the app

```powershell
python run.py
```

Open http://localhost:5000, log in with the credentials above, then:
- If no API key is stored yet, you’ll be taken to the “API Key” page to save and validate it.
- Click “Run now” to start a new analysis. You’ll see a loader with a progress bar and live logs.
- When it completes, the page refreshes with the newest Markdown brief and signals.

## Configuration & Data

- OpenAI key: stored locally in `data/openai_api_key.txt` via the in‑app form, validated via `GET /v1/models`.
- Results: last output lives in `data/last_run.json` and the AI‑only payload in `data/openai_output.json`.
- Indicators: if all are unavailable, the “Key Indicators” section is omitted from Markdown.
- Tickers: the run prioritizes tickers from your previous signals; if none exist, it auto-discovers trending tickers from Yahoo (region US). No DEFAULT_TICKERS are required.
- The app shows the last saved results by default; it only calls external APIs when you click “Run now”.

## Project Structure

```
AlphaPulse-AI/
  app/
    __init__.py           # App factory, blueprints
    auth.py               # Simple login
    routes.py             # Pages, /run and /run-stream (SSE)
    services/
      news_crawler.py     # Yahoo Finance RSS/search
      openai_summarizer.py# Prompt & parsing (Markdown + JSON signals)
      yfinance_utils.py   # Daily indicators
  templates/
    base.html             # Centered header + layout
    login.html
    index.html            # Dashboard, live counter, SSE overlay
  static/
    css/styles.css        # Dark “liquid glass” theme
  data/                   # Saved outputs & API key
  run.py                  # Entry point
  requirements.txt
```

## Notes & Limitations

- Authentication is minimal and in‑memory—sufficient for demos. Use a proper user store for production.
- Yahoo and yfinance can rate‑limit or occasionally fail; the app falls back gracefully (e.g., omitting indicators section).
- The Daily Brief strictly cites only the provided URLs; broaden crawlers if you want richer macro coverage.
- SSE requires a compatible reverse proxy configuration if you deploy behind Nginx/Apache. Disable buffering for `/run-stream`.

## Troubleshooting

- “OpenAI key missing/invalid”: Go to the API Key page and save a valid key; we validate with `/v1/models`.
- Indicators all “not available”: yfinance may be rate‑limited; try again later or cache results.
- SSE doesn’t update: Check browser console and ensure your proxy doesn’t buffer SSE.

## License

MIT
