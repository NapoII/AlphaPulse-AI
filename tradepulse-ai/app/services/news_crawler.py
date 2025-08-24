import time
from datetime import datetime, timedelta
from typing import List, Dict

import requests

# Simple NewsAPI/yahoo style RSS + Yahoo Finance search fallback

YAHOO_NEWS_SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"
YAHOO_NEWS_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
YAHOO_TRENDING = "https://query1.finance.yahoo.com/v1/finance/trending/{region}"

USER_AGENT = {
    'User-Agent': 'AlphaPulse-AI/1.0 (+https://example.com)'
}

def fetch_relevant_news(tickers: List[str]) -> List[Dict]:
    print(f"📰 Crawling Yahoo Finance news for tickers: {', '.join(tickers)}")
    items: List[Dict] = []
    cutoff = datetime.utcnow() - timedelta(days=2)

    for t in tickers:
        print(f"🔎  Fetching RSS + search for: {t}")
        # RSS headlines per ticker
        rss_url = YAHOO_NEWS_RSS.format(ticker=t)
        try:
            r = requests.get(rss_url, headers=USER_AGENT, timeout=10)
            if r.ok and '<item>' in r.text:
                # naive parse to avoid extra deps
                parts = r.text.split('<item>')[1:6]
                for p in parts:
                    title = _extract(p, '<title>', '</title>')
                    link = _extract(p, '<link>', '</link>')
                    pubDate = _extract(p, '<pubDate>', '</pubDate>')
                    if title and link:
                        items.append({
                            'ticker': t,
                            'title': title.strip(),
                            'url': link.strip(),
                            'source': 'Yahoo Finance RSS',
                            'published_at': pubDate or ''
                        })
                print(f"   ✅ RSS items: {len(parts)}")
        except Exception:
            print(f"   ⚠️  RSS fetch failed for {t}")
        time.sleep(0.3)

        # Web search fallback for broader context
        try:
            r = requests.get(YAHOO_NEWS_SEARCH, params={'q': t, 'newsCount': 5}, headers=USER_AGENT, timeout=10)
            if r.ok:
                data = r.json()
                nlist = (data.get('news', []) or [])[:5]
                for n in nlist:
                    items.append({
                        'ticker': t,
                        'title': n.get('title'),
                        'url': n.get('link'),
                        'source': n.get('publisher'),
                        'published_at': n.get('providerPublishTime')
                    })
                print(f"   ✅ Search items: {len(nlist)}")
        except Exception:
            print(f"   ⚠️  Search fetch failed for {t}")
        time.sleep(0.2)

    # Deduplicate by url
    seen = set()
    deduped = []
    for it in items:
        u = it.get('url')
        if u and u not in seen:
            seen.add(u)
            deduped.append(it)
    print(f"🧹 Deduplicated news: {len(deduped)} (from {len(items)})")
    return deduped


def fetch_trending_tickers(region: str = 'US', limit: int = 6) -> List[str]:
    """Fetch trending tickers from Yahoo Finance for a region (default US).
    Returns up to `limit` uppercase symbols, or an empty list on failure.
    """
    try:
        r = requests.get(YAHOO_TRENDING.format(region=region), headers=USER_AGENT, timeout=10)
        if r.ok:
            data = r.json() or {}
            results = (((data.get('finance') or {}).get('result') or []) or [])
            if results:
                quotes = (results[0].get('quotes') or [])
                syms = []
                for q in quotes:
                    sym = (q.get('symbol') or '').upper()
                    if sym and sym not in syms:
                        syms.append(sym)
                if limit and len(syms) > limit:
                    syms = syms[:limit]
                print(f"🔥 Trending tickers ({region}): {', '.join(syms)}")
                return syms
    except Exception:
        pass
    print("⚠️  Failed to fetch trending tickers; returning empty list")
    return []


def _extract(text: str, start: str, end: str) -> str:
    try:
        s = text.index(start) + len(start)
        e = text.index(end, s)
        return text[s:e]
    except ValueError:
        return ''
