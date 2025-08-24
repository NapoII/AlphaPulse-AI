import os
import json
from typing import List, Dict, Tuple

import requests

OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

PROMPT_EN = """
You are a financial analyst. Write in English. Create a daily market summary from the provided news and indicators.

Strict output format:
-->Markdown
(Only the full Markdown report.)

Required Markdown structure:
1) Daily Brief (single paragraph, 4-7 concise sentences) that describes the day’s key market narratives (e.g., oil prices, geopolitics, macro data) and how they impact equities. Every non-obvious claim MUST include an inline numeric citation like [1], [2], etc. Only cite sources from the Sources section you will produce below.
2) Key Indicators (very short bullet list). Include this section ONLY if at least one indicator value is present; if none are available, omit this section entirely (do NOT write "not available").
3) Per-ticker Insights for the target tickers (short bullets or mini-sections). Each claim must be grounded in the provided News and/or Indicators and include at least one inline citation [n] if it references news.
4) Sources (a numbered list 1..N). Use ONLY URLs from the provided News URLs list. Pick the most relevant 5-10 items. The numbering here must match the inline citations used above.

-->Json:
{{"signals": [
    {{"ticker": "TICKER1", "name": "Company 1", "action": "Buy"|"Sell", "reason": "1-2 sentences referencing the key news/indicators with explicit linkage (e.g., cites [n])"}},
    {{"ticker": "TICKER2", "name": "Company 2", "action": "Buy"|"Sell", "reason": "1-2 sentences referencing the key news/indicators with explicit linkage (e.g., cites [n])"}},
    {{"ticker": "TICKER3", "name": "Company 3", "action": "Buy"|"Sell", "reason": "1-2 sentences referencing the key news/indicators with explicit linkage (e.g., cites [n])"}}
]}}

Grounding & style rules:
- English only.
- Use tickers exactly as provided (uppercase); do not introduce new tickers.
- Base your analysis strictly on the provided compact News and Indicators. If information is not present, say "not available" rather than assuming.
- All claims derived from news must include inline citations [n] that refer to the numbered Sources list at the end.
- The JSON must be machine-readable: no comments, no trailing commas, no Markdown code fences.

Inputs:
- News (compact JSON): {news_compact}
- News URLs (list): {news_urls}
- Indicators (JSON): {indicators}
- Target tickers: {tickers}
"""


def generate_daily_summary_en(news: List[Dict], indicators: Dict) -> Tuple[str, Dict]:
    tickers = sorted({n.get('ticker') for n in news if n.get('ticker')} | set(indicators.keys()))

    # Compact the news to stay within token limits while preserving references
    compact, url_list = _compact_news(news)

    prompt = PROMPT_EN.format(
        news_compact=json.dumps(compact, ensure_ascii=False),
        news_urls=json.dumps(url_list, ensure_ascii=False),
        indicators=json.dumps(indicators, ensure_ascii=False),
        tickers=", ".join(tickers)
    )
    print("🤖 OpenAI prompt (first 800 chars):\n" + prompt[:800] + ("..." if len(prompt) > 800 else ""))

    from ..config_store import get_openai_key
    api_key = get_openai_key() or ''
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    body = {
        'model': OPENAI_MODEL,
        'messages': [
            { 'role': 'system', 'content': 'You are a helpful financial analyst.' },
            { 'role': 'user', 'content': prompt }
        ],
        'temperature': 0.2
    }

    markdown = ""
    signals = {}

    try:
        r = requests.post(f"{OPENAI_API_BASE}/chat/completions", headers=headers, json=body, timeout=60)
        r.raise_for_status()
        data = r.json()
        content = data['choices'][0]['message']['content']
        print("🧠 OpenAI raw content (first 800 chars):\n" + (content[:800] if isinstance(content, str) else str(content)) + ("..." if isinstance(content, str) and len(content) > 800 else ""))
        # Split Markdown and JSON using robust marker handling
        markdown, signals = _extract_markdown_and_json(content)
        print("📝 Markdown length:", len(markdown))
        try:
            print("✅ Signals parsed:", json.dumps(signals)[:400])
        except Exception:
            print("✅ Signals parsed (repr):", repr(signals)[:400])
    except Exception as e:
        markdown = f"Error calling OpenAI: {e}"
        signals = { 'signals': [] }
        print("💥 OpenAI call failed:", e)

    return markdown, signals


def _extract_markdown_and_json(content: str) -> Tuple[str, Dict]:
    """Split the LLM content into markdown and signals JSON.
    Accept markers like '-->Json:' or a line that equals 'JSON:'
    and strip optional code fences around JSON.
    """
    import re

    text = content or ''

    # Try to find the JSON marker line (case-insensitive), supporting variations
    # e.g., '-->Json:' or 'JSON:' or 'Json:' possibly with surrounding whitespace
    pattern = re.compile(r"^\s*(?:-->\s*)?json\s*:\s*$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    if not match:
        # Fallback A: try 'JSON:' within the text
        idx = text.find('\nJSON:')
        if idx != -1:
            split_at = idx + 1
            md = text[:split_at].strip()
            json_part = text[split_at + len('JSON:'):].strip()
            json_part = _strip_code_fences(json_part).strip()
            try:
                parsed = json.loads(json_part)
                if isinstance(parsed, dict) and 'signals' in parsed:
                    return md, parsed
                if isinstance(parsed, list):
                    return md, { 'signals': parsed }
            except Exception:
                pass
        # Fallback B: detect inline {"signals": ...} JSON without markers
        sig_pat = re.compile(r"\{\s*\"signals\"\s*:\s*", re.IGNORECASE)
        matches = list(sig_pat.finditer(text))
        if matches:
            start = matches[-1].start()  # position of '{'
            candidate = _cut_balanced_json(text, start)
            if candidate:
                try:
                    parsed = json.loads(candidate)
                    md = text[:start].strip()
                    if isinstance(parsed, dict) and 'signals' in parsed:
                        return md, parsed
                    if isinstance(parsed, list):
                        return md, { 'signals': parsed }
                except Exception:
                    pass
        # Could not split; return all as markdown
        return text.strip(), { 'signals': [] }
    else:
        split_at = match.start()
        md = text[:split_at].strip()
        json_part = text[match.end():].strip()

    json_part = _strip_code_fences(json_part).strip()
    try:
        parsed = json.loads(json_part)
        if isinstance(parsed, dict) and 'signals' in parsed:
            return md, parsed
        # If the top-level is a list, wrap it
        if isinstance(parsed, list):
            return md, { 'signals': parsed }
    except Exception:
        pass
    return md, { 'signals': [] }


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith('```') and s.endswith('```'):
        # remove first and last fence line
        lines = s.splitlines()
        if len(lines) >= 2:
            return '\n'.join(lines[1:-1])
    return s


def _compact_news(news: List[Dict], max_items: int = 20, per_ticker: int = 4, max_chars: int = 8000):
    """Return a compact list of news entries with only essential fields and a list of URLs.
    Strategy:
    - Keep at most per_ticker items per ticker symbol.
    - Cap total items to max_items.
    - Truncate titles to ~180 chars.
    - Include only: ticker, title, url, source, published_at.
    - Ensure the resulting JSON string stays under max_chars by trimming.
    """
    if not news:
        return [], []
    by_ticker = {}
    urls = []
    compact = []
    for item in news:
        t = (item.get('ticker') or '').upper()
        if t not in by_ticker:
            by_ticker[t] = 0
        if by_ticker[t] >= per_ticker:
            continue
        title = (item.get('title') or '').strip()
        if len(title) > 180:
            title = title[:177] + '...'
        url = (item.get('url') or '').strip()
        c = {
            'ticker': t,
            'title': title,
            'url': url,
            'source': item.get('source') or '',
            'published_at': item.get('published_at') or ''
        }
        compact.append(c)
        if url:
            urls.append(url)
        by_ticker[t] += 1
        if len(compact) >= max_items:
            break

    # Enforce character budget by trimming list if necessary
    def size_of(payload):
        try:
            return len(json.dumps(payload, ensure_ascii=False))
        except Exception:
            return 0

    while compact and size_of(compact) > max_chars:
        compact.pop()

    # Deduplicate URLs preserving order
    seen = set()
    dedup_urls = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            dedup_urls.append(u)

    return compact, dedup_urls


def _cut_balanced_json(text: str, start: int) -> str:
    """Return a balanced JSON substring starting at index 'start' (which should point to '{').
    Scans forward counting braces until balance returns to zero. Returns substring or empty if not balanced.
    """
    if start < 0 or start >= len(text) or text[start] != '{':
        return ''
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            continue
        else:
            if ch == '"':
                in_string = True
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i+1]
    return ''
