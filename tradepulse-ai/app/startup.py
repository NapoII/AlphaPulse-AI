import os
import json
from datetime import datetime

from .services.news_crawler import fetch_relevant_news
from .services.yfinance_utils import get_daily_indicators
from .services.openai_summarizer import generate_daily_summary_en


def initial_run(root_path):
    tickers = os.getenv('DEFAULT_TICKERS', 'AAPL,MSFT,GOOGL,AMZN,TSLA,SPY').split(',')
    tickers = [t.strip().upper() for t in tickers if t.strip()]

    news = fetch_relevant_news(tickers)
    indicators = get_daily_indicators(tickers)
    markdown, signals = generate_daily_summary_en(news, indicators)

    data_path = os.path.join(root_path, '..', 'data', 'last_run.json')
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'news': news,
            'indicators': indicators,
            'markdown': markdown,
            'signals': signals
        }, f, ensure_ascii=False, indent=2)
