import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash, Response
from flask import stream_with_context
from flask_login import login_required
from .services.news_crawler import fetch_relevant_news, fetch_trending_tickers
from .services.yfinance_utils import get_daily_indicators
from .services.openai_summarizer import generate_daily_summary_en
from .config_store import get_openai_key, set_openai_key, validate_openai_key

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    print("🏠 Rendering index page")
    # Ensure OpenAI key exists; if missing, ask user
    if not get_openai_key():
        print("🔐 Missing OpenAI key; redirecting to /api-key")
        return redirect(url_for('main.api_key'))
    # Load last run if available
    data_path = os.path.join(current_app.root_path, '..', 'data', 'last_run.json')
    news_items = []
    summary_markdown = None
    signals_json = None

    last_updated = None
    if os.path.exists(data_path):
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
                # Basic relevance filter: must have title+url; keep top 30
                raw_news = payload.get('news', [])
                news_items = [n for n in raw_news if (n.get('title') and n.get('url'))][:30]
                summary_markdown = payload.get('markdown')
                signals_json = payload.get('signals')
                last_updated = payload.get('timestamp')
        except Exception:
            pass

    print(f"📄 Loaded last run: news={len(news_items)} markdown={'yes' if summary_markdown else 'no'} signals={'yes' if signals_json else 'no'}")
    return render_template('index.html', news_items=news_items, summary_markdown=summary_markdown, signals_json=signals_json, last_updated=last_updated)
@main_bp.route('/run', methods=['POST'])
@login_required
def run_now():
    print("🚀 Run now triggered")
    if not get_openai_key():
        return redirect(url_for('main.api_key'))
    # Base tickers from previous signals if available; otherwise discover trending tickers
    tickers = []

    # If a previous run exists with signals, prioritize those tickers
    data_path = os.path.join(current_app.root_path, '..', 'data', 'last_run.json')
    if os.path.exists(data_path):
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                prev = json.load(f)
                prev_signals = (prev or {}).get('signals', {}).get('signals', [])
                prev_tickers = [s.get('ticker') for s in prev_signals if s.get('ticker')]
                # Keep order: previous signals first, then defaults
                merged = []
                for t in prev_tickers + tickers:
                    tt = (t or '').upper()
                    if tt and tt not in merged:
                        merged.append(tt)
                tickers = merged
        except Exception:
            pass

    if not tickers:
        tickers = fetch_trending_tickers('US', limit=6) or []

    news = fetch_relevant_news(tickers)
    indicators = get_daily_indicators(tickers)

    markdown, signals = generate_daily_summary_en(news, indicators)
    print("🧷 Summary markdown present:", bool(markdown))
    print("📦 Signals keys:", list((signals or {}).keys()))

    # Persist
    data_path = os.path.join(current_app.root_path, '..', 'data', 'last_run.json')
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'news': news,
            'indicators': indicators,
            'markdown': markdown,
            'signals': signals
        }, f, ensure_ascii=False, indent=2)

    # Also write a dedicated OpenAI output file for external reuse
    ai_out_path = os.path.join(current_app.root_path, '..', 'data', 'openai_output.json')
    with open(ai_out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'markdown': markdown,
            'signals': signals
        }, f, ensure_ascii=False, indent=2)

    print("✅ Run completed; redirecting to index")
    return redirect(url_for('main.index'))


@main_bp.route('/run-stream')
@login_required
def run_stream():
    print("📡 SSE run stream started")
    if not get_openai_key():
        return redirect(url_for('main.api_key'))

    def sse_event(event: str, data: dict) -> str:
        try:
            payload = json.dumps(data, ensure_ascii=False)
        except Exception:
            payload = json.dumps({'message': str(data)})
        return f"event: {event}\ndata: {payload}\n\n"

    @stream_with_context
    def generate():
        try:
            yield sse_event('progress', {'message': 'Starting run…', 'pct': 1})

            # Base tickers from env or default list
            default_tickers = os.getenv('DEFAULT_TICKERS', 'AAPL,MSFT,GOOGL,AMZN,TSLA,SPY')
            tickers = [t.strip().upper() for t in default_tickers.split(',') if t.strip()]

            # Prioritize previous signal tickers if available
            data_path = os.path.join(current_app.root_path, '..', 'data', 'last_run.json')
            if os.path.exists(data_path):
                try:
                    with open(data_path, 'r', encoding='utf-8') as f:
                        prev = json.load(f)
                        prev_signals = (prev or {}).get('signals', {}).get('signals', [])
                        prev_tickers = [s.get('ticker') for s in prev_signals if s.get('ticker')]
                        merged = []
                        for t in prev_tickers + tickers:
                            tt = (t or '').upper()
                            if tt and tt not in merged:
                                merged.append(tt)
                        tickers = merged
                except Exception:
                    pass

            yield sse_event('progress', {'message': f'Tickers: {", ".join(tickers)}', 'pct': 5})

            yield sse_event('progress', {'message': 'Fetching news…', 'pct': 10})
            news = fetch_relevant_news(tickers)
            yield sse_event('progress', {'message': f'News fetched: {len(news)} items', 'pct': 40})

            yield sse_event('progress', {'message': 'Fetching indicators…', 'pct': 45})
            indicators = get_daily_indicators(tickers)
            ind_count = len([k for k,v in (indicators or {}).items() if v])
            yield sse_event('progress', {'message': f'Indicators fetched for {ind_count} tickers', 'pct': 60})

            yield sse_event('progress', {'message': 'Calling OpenAI…', 'pct': 65})
            markdown, signals = generate_daily_summary_en(news, indicators)
            yield sse_event('progress', {'message': 'OpenAI summary parsed', 'pct': 90})

            # Persist results
            ts = datetime.utcnow().isoformat() + 'Z'
            store_path = os.path.join(current_app.root_path, '..', 'data', 'last_run.json')
            os.makedirs(os.path.dirname(store_path), exist_ok=True)
            with open(store_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': ts,
                    'news': news,
                    'indicators': indicators,
                    'markdown': markdown,
                    'signals': signals
                }, f, ensure_ascii=False, indent=2)

            ai_out_path = os.path.join(current_app.root_path, '..', 'data', 'openai_output.json')
            with open(ai_out_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': ts,
                    'markdown': markdown,
                    'signals': signals
                }, f, ensure_ascii=False, indent=2)

            yield sse_event('progress', {'message': 'Saved results', 'pct': 98})
            yield sse_event('done', {'message': 'Run completed'})
        except Exception as e:
            err = str(e)
            print('💥 SSE run error:', err)
            yield sse_event('progress', {'message': f'Error: {err}', 'pct': 100})
            yield sse_event('done', {'message': 'Run failed'})

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    }
    return Response(generate(), mimetype='text/event-stream', headers=headers)


@main_bp.route('/api-key', methods=['GET', 'POST'])
@login_required
def api_key():
    print("🔑 API key page")
    """Prompt user for OpenAI API key if not present or invalid."""
    if request.method == 'POST':
        key = request.form.get('api_key', '')
        ok, msg = validate_openai_key(key)
        if ok:
            set_openai_key(key)
            print("✅ API key validated and saved")
            flash('OpenAI API key saved.', 'success')
            return redirect(url_for('main.index'))
        else:
            print("❌ API key validation failed:", msg)
            flash(f'Key validation failed: {msg}', 'danger')
    return render_template('api_key.html')
