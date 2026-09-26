"""Local FastAPI service for market data, simulations, and the React build."""
import argparse
import asyncio
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from engine import COINS, compare, number
from stress import PRESETS, build_path, run_stress

ROOT = Path(__file__).resolve().parent
IDS = {'BTC': 1, 'ETH': 1027, 'USDC': 3408}
SLUGS = {'BTC': 'bitcoin', 'ETH': 'ethereum', 'USDC': 'usd-coin'}
BASE_URL = 'https://pro-api.coinmarketcap.com'
WINDOWS = [
    {'id': 'history-2021', 'label': '2021.05 — 2022.05', 'start': '2021-05-01', 'end': '2022-05-02'},
    {'id': 'history-2022', 'label': '2022.01 — 2023.01', 'start': '2022-01-01', 'end': '2023-01-02'},
    {'id': 'history-2023', 'label': '2023.01 — 2024.01', 'start': '2023-01-01', 'end': '2024-01-02'},
]


class CMCError(Exception):
    def __init__(self, message, http_status=502, code=None):
        super().__init__(message)
        self.http_status = http_status
        self.code = code


def utcnow():
    return datetime.now(timezone.utc)


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp needs timezone')
    return parsed.astimezone(timezone.utc)


def parse_latest(payload):
    try:
        data = payload['data']
        if not isinstance(data, list) or str(payload['status']['error_code']) != '0':
            raise ValueError()
        prices, stamps = {}, {}
        for symbol, coin_id in IDS.items():
            candidates = [item for item in data if item['id'] == coin_id and item['symbol'] == symbol]
            if len(candidates) != 1:
                raise ValueError()
            quotes = [q for q in candidates[0]['quote'] if q['symbol'] == 'USD' and q['id'] == 2781]
            if len(quotes) != 1:
                raise ValueError()
            quote = quotes[0]
            prices[symbol] = str(number(quote['price'], symbol, Decimal('1e-18'), Decimal('1e12')))
            stamps[symbol] = timestamp(quote['last_updated']).isoformat()
        return {'prices': prices, 'timestamps': stamps, 'as_of': min(stamps.values()),
                'credit_count': payload['status'].get('credit_count')}
    except (ValueError, KeyError, TypeError, AttributeError):
        raise CMCError('CMC latest quote fields are missing or malformed; incomplete market data was not used') from None


def parse_history(payload, start, end):
    """Validate complete daily data per asset, including the baseline, without filling gaps."""
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        expected = [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]
        all_prices = {}
        for symbol, coin_id in IDS.items():
            item = payload['data'][str(coin_id)]
            if item['id'] != coin_id:
                raise ValueError()
            closes = {}
            for record in item['quotes']:
                day = timestamp(record['time_open']).date().isoformat()
                if day in closes:
                    raise ValueError()
                closes[day] = number(record['quote']['USD']['close'], symbol, Decimal('1e-18'), Decimal('1e12'))
            if set(closes) != set(expected):
                raise ValueError()
            all_prices[symbol] = closes
        with localcontext() as context:
            context.prec = 40
            return [{c: str(all_prices[c][d] / all_prices[c][start]) for c in COINS} for d in expected]
    except (ValueError, KeyError, TypeError, AttributeError):
        raise CMCError('Historical data is missing, duplicated, or invalid; this scenario is unavailable') from None


def load_key():
    # Support existing environment variable names without printing or sending the key to the browser.
    values = {}
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                name, value = line.split('=', 1)
                values[name.strip()] = value.strip().strip('\"\'')
    return next((os.environ.get(name) or values.get(name) for name in
                 ('CMC_API_KEY', 'CMC_API', 'COINMARKETCAP_API_KEY')
                 if os.environ.get(name) or values.get(name)), '')


class Market:
    def __init__(self, cache_dir=None):
        self.cache_dir = cache_dir or ROOT / '.cache'
        self.cache_dir.mkdir(exist_ok=True)
        self.cached = None
        self.next_refresh = 0
        self.last_error = None
        self.snapshots = {}
        self.lock = threading.Lock()
        try:
            cached = json.loads((self.cache_dir / 'latest.json').read_text(encoding='utf-8'))
            self.cached = parse_latest(cached['response'])
            self.cached['fetched_at'] = cached['captured_at']
        except (OSError, ValueError, KeyError, CMCError):
            pass  # Request live quotes when the cache is missing or invalid.

    def request(self, path, params):
        key = load_key()
        if not key:
            raise CMCError('CMC_API_KEY (or CMC_API) is not configured on the server', 503)
        url = BASE_URL + path + '?' + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={'X-CMC_PRO_API_KEY': key, 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = response.read(4_000_000)
            payload = json.loads(body)
        except urllib.error.HTTPError as error:
            # Do not forward upstream details that could contain the API key or request headers.
            messages = {401: 'The CMC API key is invalid or inactive', 403: 'The CMC plan does not support this endpoint',
                        429: 'CMC request or credit limit reached; try again later'}
            raise CMCError(messages.get(error.code, 'The CMC service is temporarily unavailable'), error.code) from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise CMCError('Unable to retrieve CMC market data; check the network or try again later') from None
        if not isinstance(payload, dict) or str(payload.get('status', {}).get('error_code')) != '0':
            raise CMCError('CMC returned a failure status; the response was not used')
        return payload

    def remember(self, snapshot):
        encoded = json.dumps(snapshot, sort_keys=True).encode()
        snapshot = {**snapshot, 'snapshot_id': hashlib.sha256(encoded).hexdigest()[:24]}
        self.snapshots[snapshot['snapshot_id']] = snapshot
        while len(self.snapshots) > 32:
            del self.snapshots[next(iter(self.snapshots))]
        return snapshot

    def latest(self, mode='live'):
        with self.lock:
            if mode == 'recorded':
                try:
                    evidence = json.loads((ROOT / 'evidence/latest.json').read_text(encoding='utf-8'))
                    snapshot = parse_latest(evidence['response'])
                except (OSError, ValueError, KeyError):
                    raise CMCError('No usable recorded quote file was found', 503) from None
                return self.remember({**snapshot, 'fetched_at': evidence['captured_at'], 'mode': 'recorded',
                                      'stale': True, 'warning': 'Recorded replay: uses previously captured real CMC quotes, not current market data.',
                                      'source': 'CoinMarketCap /v3/cryptocurrency/quotes/latest'})
            if mode != 'live':
                raise ValueError('Market data mode is invalid')
            if time.monotonic() >= self.next_refresh:
                self.next_refresh = time.monotonic() + 60
                try:
                    payload = self.request('/v3/cryptocurrency/quotes/latest', {'id': '1,1027,3408', 'convert': 'USD'})
                    parsed = parse_latest(payload)
                    age = (utcnow() - timestamp(parsed['as_of'])).total_seconds()
                    if not -300 <= age <= 86400:
                        raise CMCError('The CMC quote timestamp is invalid or more than 24 hours old')
                    self.cached = {**parsed, 'fetched_at': utcnow().isoformat()}
                    self.last_error = None
                    cache = {'captured_at': self.cached['fetched_at'], 'response': payload}
                    temp = self.cache_dir / 'latest.tmp'
                    temp.write_text(json.dumps(cache), encoding='utf-8')
                    temp.replace(self.cache_dir / 'latest.json')
                except CMCError as error:
                    self.last_error = str(error)
            if self.cached is None or (utcnow() - timestamp(self.cached['as_of'])).total_seconds() > 86400:
                raise CMCError(self.last_error or 'The cached quote is more than 24 hours old; refresh or explicitly select recorded replay', 503)
            stale = bool(self.last_error) or (utcnow() - timestamp(self.cached['as_of'])).total_seconds() > 300
            return self.remember({**self.cached, 'mode': 'live', 'stale': stale,
                                  'warning': (self.last_error or 'The quote is more than 5 minutes old; cached market data is in use') if stale else '',
                                  'source': 'CoinMarketCap /v3/cryptocurrency/quotes/latest'})

    def scenarios(self):
        scenarios = []
        for window in WINDOWS:
            try:
                self.history(window['id'])
                available, reason = True, ''
            except CMCError as error:
                available, reason = False, str(error)
            scenarios.append({**window, 'available': available, 'reason': reason})
        return scenarios

    def history(self, scenario):
        window = next((w for w in WINDOWS if w['id'] == scenario), None)
        if window is None:
            raise CMCError('Unknown historical scenario', 400)
        try:
            data = json.loads((self.cache_dir / f'{scenario}.json').read_text(encoding='utf-8'))
            path = parse_history(data['response'], window['start'], window['end'])
            return path, {**window, 'fetched_at': data['captured_at'], 'source': '/v2/cryptocurrency/ohlcv/historical'}
        except (OSError, ValueError, KeyError):
            raise CMCError('Complete historical data is unavailable; run python server.py --fetch-history with an eligible CMC plan', 503) from None

    def get_snapshot(self, body):
        """Apply the same snapshot age and provenance checks to every calculation endpoint."""
        if not isinstance(body, dict):
            raise ValueError('Request body must be a JSON object')
        snapshot_id = body.get('snapshot_id')
        if not isinstance(snapshot_id, str):
            raise CMCError('The quote snapshot has expired; refresh market data', 409)
        with self.lock:
            snapshot = self.snapshots.get(snapshot_id)
        if snapshot is None:
            raise CMCError('The quote snapshot has expired; refresh market data', 409)
        age = (utcnow() - timestamp(snapshot['as_of'])).total_seconds()
        if snapshot['mode'] == 'live' and age > 86400:
            raise CMCError('The quote is more than 24 hours old; refresh market data', 409)
        snapshot = {**snapshot}
        if snapshot['mode'] == 'live' and age > 300:
            snapshot.update(stale=True, warning='The pinned quote snapshot is more than 5 minutes old; refresh to retrieve a new quote.')
        return snapshot

    def stress(self, body):
        snapshot = self.get_snapshot(body)
        result = run_stress(body.get('inputs'), snapshot['prices'], body.get('target_payments'), body.get('scenarios'))
        return {'version': 2, 'generated_at': utcnow().isoformat(), 'market': snapshot,
                'inputs': body['inputs'], 'stress': result}

    def simulate(self, body):
        snapshot = self.get_snapshot(body)
        scenario = body.get('scenario', 'custom')
        definition = body.get('scenario_definition')
        if definition is not None:
            if not isinstance(body.get('inputs'), dict):
                raise ValueError('Input must be an object')
            path = build_path(body['inputs'].get('start'), definition)
            source = {**definition, 'kind': 'hypothetical'}
        elif scenario == 'custom':
            path, source = None, {'id': 'custom', 'label': 'User-defined one-time shock'}
        else:
            path, source = self.history(scenario)
        result = compare(body.get('inputs'), snapshot['prices'], path, hypothetical=definition is not None)
        return {'version': 1, 'generated_at': utcnow().isoformat(), 'market': snapshot,
                'scenario': source, 'inputs': body['inputs'], 'result': result}


def create_app(market=None, frontend_dir=None):
    """Reuse the market service and expose only static files from the frontend build."""
    market = market or Market()
    frontend_dir = Path(frontend_dir) if frontend_dir is not None else ROOT / 'frontend' / 'dist'
    app = FastAPI(title='Runway API', docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def protect_request(request: Request, call_next):
        host = request.headers.get('host', '')
        try:
            parsed = urllib.parse.urlsplit('http://' + host)
            trusted = parsed.hostname in ('127.0.0.1', 'localhost') and parsed.netloc == host
            trusted = trusted and parsed.username is None and parsed.password is None
            if parsed.port is not None:
                trusted = trusted and 0 < parsed.port <= 65535
        except ValueError:
            trusted = False
        # Vite uses port 5173; allow only the current origin and these two local development origins.
        origins = {'http://' + host, 'http://127.0.0.1:5173', 'http://localhost:5173'}
        if not trusted:
            response = JSONResponse({'error': 'Local access only'}, status_code=403)
        elif request.method not in ('GET', 'HEAD') and request.headers.get('origin') not in (None, *origins):
            response = JSONResponse({'error': 'Cross-origin request rejected'}, status_code=403)
        else:
            response = await call_next(request)
        response.headers.update({
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        })
        return response

    @app.exception_handler(CMCError)
    async def handle_market_error(request: Request, error: CMCError):
        status = error.http_status if error.http_status in (400, 409, 503) else 503
        return JSONResponse({'error': str(error)}, status_code=status)

    @app.exception_handler(ValueError)
    async def handle_value_error(request: Request, error: ValueError):
        return JSONResponse({'error': str(error)}, status_code=400)

    @app.exception_handler(OSError)
    async def handle_file_error(request: Request, error: OSError):
        return JSONResponse({'error': 'Local file read failed or the request timed out'}, status_code=503)

    @app.get('/')
    def read_index():
        index = frontend_dir / 'index.html'
        if not index.is_file():
            return JSONResponse({'error': 'The frontend has not been built; run npm --prefix frontend install and npm --prefix frontend run build'}, status_code=503)
        return FileResponse(index)

    @app.get('/api/market')
    def read_market(mode: str = 'live'):
        return market.latest(mode)

    @app.get('/api/scenarios')
    def read_scenarios():
        return market.scenarios()

    @app.get('/api/stress-presets')
    def read_stress_presets():
        return PRESETS

    @app.post('/api/stress')
    @app.post('/api/simulate')
    async def simulate(request: Request):
        if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
            return JSONResponse({'error': 'Send a JSON request body'}, status_code=415)
        try:
            declared = request.headers.get('content-length')
            if declared is not None and not 0 < int(declared) <= 16384:
                return JSONResponse({'error': 'Invalid request size; maximum is 16 KB'}, status_code=413)
            # Limit streamed requests too, so Content-Length cannot bypass the size cap.
            body = bytearray()
            async with asyncio.timeout(10):
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 16384:
                        return JSONResponse({'error': 'Invalid request size; maximum is 16 KB'}, status_code=413)
            if not body:
                return JSONResponse({'error': 'Invalid request size; maximum is 16 KB'}, status_code=413)
            payload = json.loads(body)
            # Run synchronous calculations in the thread pool to avoid blocking other ASGI requests.
            operation = market.stress if request.url.path == '/api/stress' else market.simulate
            return await run_in_threadpool(operation, payload)
        except (ValueError, TypeError, KeyError, RecursionError):
            return JSONResponse({'error': 'Invalid input: check numeric ranges, dates, and required fields'}, status_code=400)

    # Do not mount the project root, preventing downloads of secrets, source, cache, or evidence files.
    @app.get('/assets/{filename:path}')
    def read_asset(filename: str):
        assets = (frontend_dir / 'assets').resolve()
        target = (assets / filename).resolve()
        if not target.is_relative_to(assets) or not target.is_file():
            return JSONResponse({'error': 'File not found'}, status_code=404)
        return FileResponse(target)

    return app


def fetch_history(market):
    for window in WINDOWS:
        start = (date.fromisoformat(window['start']) - timedelta(days=1)).isoformat()
        payload = market.request('/v2/cryptocurrency/ohlcv/historical',
                                 {'id': '1,1027,3408', 'time_start': start, 'time_end': window['end'],
                                  'time_period': 'daily', 'interval': 'daily', 'convert': 'USD', 'skip_invalid': 'false'})
        path = parse_history(payload, window['start'], window['end'])
        record = {'captured_at': utcnow().isoformat(), 'response': payload}
        destination = market.cache_dir / f"{window['id']}.json"
        temp = destination.with_suffix('.tmp')
        temp.write_text(json.dumps(record), encoding='utf-8')
        temp.replace(destination)
        print(f"{window['id']}: {len(path)} complete days; credits={payload['status'].get('credit_count')}")


def probe(market):
    requests = [('map', '/v1/cryptocurrency/map', {'symbol': 'BTC,ETH,USDC'}),
                ('latest', '/v3/cryptocurrency/quotes/latest', {'id': '1,1027,3408', 'convert': 'USD'}),
                ('historical', '/v2/cryptocurrency/ohlcv/historical',
                 {'id': '1', 'time_start': '2026-09-16', 'time_end': '2026-09-18', 'time_period': 'daily', 'convert': 'USD'})]
    for name, path, params in requests:
        try:
            response = market.request(path, params)
            if name == 'map':
                for symbol, coin_id in IDS.items():
                    if not any(i['id'] == coin_id and i['slug'] == SLUGS[symbol] and i['symbol'] == symbol for i in response['data']):
                        raise CMCError('Asset ID validation failed')
            if name == 'latest':
                parse_latest(response)
            record = {'captured_at': utcnow().isoformat(), 'request': {'method': 'GET',
                       'url': BASE_URL + path + '?' + urllib.parse.urlencode(params),
                       'authentication': 'X-CMC_PRO_API_KEY: [REDACTED]'}, 'http_status': 200, 'response': response}
            # Redact the key before writing evidence even though quote data normally excludes it.
            text = json.dumps(record, ensure_ascii=False, indent=2).replace(load_key(), '[REDACTED]')
            (ROOT / 'evidence').mkdir(exist_ok=True)
            (ROOT / 'evidence' / f'{name}.json').write_text(text, encoding='utf-8')
            print(f"{name}: HTTP 200; credits={response['status'].get('credit_count')}")
        except CMCError as error:
            print(f'{name}: HTTP {error.http_status}; {error}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--fetch-history', action='store_true', help='Download and validate three historical scenarios with an eligible plan (about 36 credits)')
    parser.add_argument('--probe', action='store_true', help='Validate endpoints and update redacted evidence (about 1-2 credits)')
    args = parser.parse_args()
    market = Market()
    if args.fetch_history or args.probe:
        try:
            fetch_history(market) if args.fetch_history else probe(market)
        except CMCError as error:
            print(str(error))
            raise SystemExit(1)
    else:
        uvicorn.run(create_app(market), host='127.0.0.1', port=args.port, access_log=False)
