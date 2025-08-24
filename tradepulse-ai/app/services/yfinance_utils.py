from typing import List, Dict
import yfinance as yf


def get_daily_indicators(tickers: List[str]) -> Dict:
    print(f"📈 Fetching daily indicators for: {', '.join(tickers)}")
    out = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            info = tk.info or {}
            hist = tk.history(period='5d', interval='1d')
            last_close = float(hist['Close'].iloc[-1]) if not hist.empty else None
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else None
            change_pct = ((last_close - prev_close) / prev_close * 100.0) if last_close and prev_close else None
            out[t] = {
                'price': last_close,
                'prev_close': prev_close,
                'change_pct': change_pct,
                'market_cap': info.get('marketCap'),
                'pe_ratio': info.get('trailingPE') or info.get('forwardPE'),
                'sector': info.get('sector'),
                'short_name': info.get('shortName') or t
            }
            print(f"   ✅ {t}: price={last_close} change={change_pct}%")
        except Exception as e:
            print(f"   ⚠️  Failed {t}: {e}")
            out[t] = {'error': 'fetch_failed'}
    return out
