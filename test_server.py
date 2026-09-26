import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import server
from server import Market, CMCError, parse_latest, parse_history
from test_engine import inputs
from stress import PRESETS

ROOT = Path(__file__).parent
LATEST = json.loads((ROOT / 'evidence/latest.json').read_text(encoding='utf-8'))['response']


class ParsingTests(unittest.TestCase):
    def test_actual_cmc_v3_array_and_usdc_price(self):
        result = parse_latest(LATEST)
        self.assertEqual(set(result['prices']), {'BTC', 'ETH', 'USDC'})
        self.assertNotEqual(result['prices']['USDC'], '1')
        self.assertEqual(result['credit_count'], 1)

    def test_missing_asset_or_nonfinite_quote_rejected(self):
        for transform in ['missing', 'nan', 'timestamp']:
            payload = copy.deepcopy(LATEST)
            if transform == 'missing':
                payload['data'].pop()
            elif transform == 'nan':
                payload['data'][0]['quote'][0]['price'] = 'NaN'
            else:
                payload['data'][0]['quote'][0].pop('last_updated')
            with self.subTest(transform=transform), self.assertRaises(CMCError):
                parse_latest(payload)

    def test_historical_relative_path_and_missing_dates(self):
        payload = {'data': {str(i): {'id': i, 'quotes': [
            {'time_open': f'2022-01-0{day}T00:00:00Z', 'quote': {'USD': {'close': price}}}
            for day, price in [(1, 100), (2, 80), (3, 120)]]} for i in [1, 1027, 3408]}}
        result = parse_history(payload, '2022-01-01', '2022-01-03')
        self.assertEqual(result[1]['BTC'], '0.8')
        payload['data']['1027']['quotes'].pop(1)
        with self.assertRaises(CMCError):
            parse_history(payload, '2022-01-01', '2022-01-03')

    def test_quote_failure_uses_marked_cache_and_expired_cache_fails(self):
        now = datetime.now(timezone.utc)
        payload = copy.deepcopy(LATEST)
        for item in payload['data']:
            item['quote'][0]['last_updated'] = now.isoformat()
        with tempfile.TemporaryDirectory() as folder:
            market = Market(Path(folder))
            with patch.object(market, 'request', return_value=payload):
                first = market.latest()
            market.next_refresh = 0
            with patch.object(market, 'request', side_effect=CMCError('Connection failed')):
                fallback = market.latest()
            self.assertTrue(fallback['stale'])
            self.assertEqual(first['prices'], fallback['prices'])
            market.cached['as_of'] = (now - timedelta(days=2)).isoformat()
            market.next_refresh = 0
            with patch.object(market, 'request', side_effect=CMCError('Connection failed')):
                with self.assertRaises(CMCError):
                    market.latest()


class HTTPTests(unittest.TestCase):
    def test_live_and_custom_price_modes(self):
        snapshot = self.market.remember({**parse_latest(LATEST), 'mode': 'live', 'as_of': server.utcnow().isoformat()})
        targets = {'BTC': '40000', 'ETH': '1000', 'USDC': '0'}
        body = {'snapshot_id': snapshot['snapshot_id'], 'scenario': 'custom-prices',
                'inputs': inputs(start='2028-01-31', target_prices=targets)}
        response = self.client.post('/api/simulate', json=body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result']['path'][1]['prices'], targets)
        body['scenario'] = 'live'
        response = self.client.post('/api/simulate', json=body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result']['path'][-1]['prices'], snapshot['prices'])
        body['scenario'] = 'custom-prices'
        del body['inputs']['target_prices']
        self.assertEqual(self.client.post('/api/simulate', json=body).status_code, 400)

    def test_public_hosts_https_origin_and_cross_instance_snapshot(self):
        with patch.dict('os.environ', {'ALLOWED_HOSTS': 'runway.example',
                                     'SNAPSHOT_SECRET': 'test-secret-' * 4}):
            first = Market(Path(self.temp.name))
            second = Market(Path(self.temp.name))
            with TestClient(server.create_app(first), base_url='https://runway.example') as client:
                response = client.get('/api/market?mode=recorded')
                self.assertEqual(response.status_code, 200)
                snapshot = response.json()
            with TestClient(server.create_app(second), base_url='https://runway.example') as client:
                body = {'snapshot_id': snapshot['snapshot_id'], 'inputs': inputs()}
                response = client.post('/api/simulate', json=body, headers={'Origin': 'https://runway.example'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['market']['prices'], snapshot['prices'])
                for origin in ['https://evil.test', 'http://runway.example', 'http://localhost:5173']:
                    self.assertEqual(client.post('/api/simulate', json=body,
                                                 headers={'Origin': origin}).status_code, 403)
                self.assertEqual(client.get('/api/scenarios', headers={'Host': 'evil.test'}).status_code, 403)
                body['snapshot_id'] = 'X' + snapshot['snapshot_id'][1:]
                self.assertEqual(client.post('/api/simulate', json=body).status_code, 409)
                body['snapshot_id'] = snapshot['snapshot_id']
                with patch('server.utcnow', return_value=datetime.now(timezone.utc) + timedelta(days=2)):
                    self.assertEqual(client.post('/api/simulate', json=body).status_code, 409)

    def test_vercel_entrypoint_temp_cache_and_automatic_hostname(self):
        self.assertIsInstance(server.app, server.FastAPI)
        with patch.dict('os.environ', {'VERCEL': '1', 'VERCEL_URL': 'runway-preview.vercel.app',
                                     'SNAPSHOT_SECRET': 'test-secret-' * 4}), \
                patch('server.tempfile.gettempdir', return_value=self.temp.name):
            market = Market()
            self.assertTrue(market.cache_dir.is_relative_to(Path(self.temp.name)))
            with TestClient(server.create_app(market), base_url='https://runway-preview.vercel.app') as client:
                self.assertEqual(client.get('/api/market?mode=recorded').status_code, 200)
                self.assertEqual(client.get('/api/scenarios', headers={'Host': 'other.vercel.app'}).status_code, 403)

    def test_missing_deployment_secret_does_not_spend_cmc_credits(self):
        with patch.dict('os.environ', {'VERCEL': '1', 'SNAPSHOT_SECRET': ''}):
            market = Market(Path(self.temp.name))
            with patch.object(market, 'request', side_effect=AssertionError('Do not call CMC without a signing secret')):
                with self.assertRaises(CMCError) as raised:
                    market.latest()
                self.assertEqual(raised.exception.http_status, 503)

    def test_cache_write_failure_keeps_valid_quote(self):
        payload = copy.deepcopy(LATEST)
        for item in payload['data']:
            item['quote'][0]['last_updated'] = datetime.now(timezone.utc).isoformat()
        with patch.object(self.market, 'request', return_value=payload), \
                patch('server.tempfile.NamedTemporaryFile', side_effect=OSError('Read-only filesystem')):
            snapshot = self.market.latest()
        self.assertEqual(snapshot['mode'], 'live')
        self.assertFalse(snapshot['stale'])

    def test_stress_and_drilldown_use_same_snapshot(self):
        snapshot = self.client.get('/api/market?mode=recorded').json()
        body = {'snapshot_id': snapshot['snapshot_id'], 'inputs': inputs(),
                'target_payments': 9, 'scenarios': [PRESETS[0], PRESETS[-1]]}
        with patch.object(self.market, 'request', side_effect=AssertionError('Market data must not be requested again')):
            response = self.client.post('/api/stress', json=body)
            self.assertEqual(response.status_code, 200)
            report = response.json()
            self.assertEqual(report['market']['snapshot_id'], snapshot['snapshot_id'])
            self.assertEqual(len(report['stress']['rows']), 13)
            detail = self.client.post('/api/simulate', json={**body, 'scenario_definition': PRESETS[0]})
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()['scenario']['kind'], 'hypothetical')
            self.assertEqual(detail.json()['result']['strategies'][1]['covered_payments'],
                             report['stress']['rows'][3]['cells'][0]['covered_payments'])
        self.assertEqual(len(self.client.get('/api/stress-presets').json()), 5)
        for content, headers, status in [(b'{}', {'Origin': 'https://evil.test'}, 403),
                                         (b'{}', {}, 409), (b' '*16385, {}, 413),
                                         (b'[]', {}, 400)]:
            response = self.client.post('/api/stress', content=content,
                                        headers={'Content-Type': 'application/json', **headers})
            self.assertEqual(response.status_code, status)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.market = Market(Path(self.temp.name))
        self.client = TestClient(server.create_app(self.market), base_url='http://127.0.0.1:8000')
        self.addCleanup(self.client.close)

    def test_private_files_not_served(self):
        for path in ['/.env', '/server.py', '/evidence/latest.json', '/../.env', '/.git/config',
                     '/assets/../.env', '/assets/%2e%2e/%2e%2e/.env']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_recorded_mode_simulation_and_invalid_input(self):
        response = self.client.get('/api/market?mode=recorded')
        self.assertEqual(response.status_code, 200)
        snapshot = response.json()
        self.assertEqual(snapshot['mode'], 'recorded')
        body = {'snapshot_id': snapshot['snapshot_id'], 'scenario': 'custom', 'inputs': inputs()}
        response = self.client.post('/api/simulate', json=body)
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(len(report['result']['strategies']), 2)
        self.assertEqual(report['market']['mode'], 'recorded')
        self.assertIsInstance(report['result']['initial_total'], str)
        body['inputs']['cash'] = '-1'
        self.assertEqual(self.client.post('/api/simulate', json=body).status_code, 400)

    def test_cross_origin_and_unknown_snapshot_rejected(self):
        response = self.client.post('/api/simulate', json={}, headers={'Origin': 'https://evil.test'})
        self.assertEqual(response.status_code, 403)
        response = self.client.post('/api/simulate', json={'snapshot_id': 'unknown', 'inputs': {}})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get('/api/scenarios', headers={'Host': 'evil.test'}).status_code, 403)

    def test_local_development_origin_and_security_headers(self):
        for origin in ['http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:8000']:
            response = self.client.post('/api/simulate', json={}, headers={'Origin': origin})
            self.assertEqual(response.status_code, 409)
        response = self.client.get('/api/scenarios')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 3)
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])

    def test_malformed_oversized_and_wrong_content_type(self):
        for content, headers, status in [
            ('{', {'Content-Type': 'application/json'}, 400),
            ('[]', {'Content-Type': 'application/json'}, 400),
            ('', {'Content-Type': 'application/json'}, 413),
            (' ' * 16385, {'Content-Type': 'application/json'}, 413),
            ('{}', {'Content-Type': 'text/plain'}, 415),
        ]:
            with self.subTest(status=status, size=len(content)):
                response = self.client.post('/api/simulate', content=content, headers=headers)
                self.assertEqual(response.status_code, status)
                self.assertIn('error', response.json())
        self.assertEqual(self.client.get('/api/market?mode=invalid').status_code, 400)

    def test_upstream_failure_does_not_leak_details(self):
        with patch.object(self.market, 'latest', side_effect=CMCError('Market data is temporarily unavailable')):
            response = self.client.get('/api/market')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'error': 'Market data is temporarily unavailable'})

    def test_built_frontend_and_missing_build(self):
        with tempfile.TemporaryDirectory() as folder:
            dist = Path(folder)
            client = TestClient(server.create_app(self.market, dist), base_url='http://localhost:8000')
            with client:
                response = client.get('/')
                self.assertEqual(response.status_code, 503)
                self.assertIn('npm', response.text)
                (dist / 'index.html').write_text('<div id="root"></div>', encoding='utf-8')
                (dist / 'assets').mkdir()
                (dist / 'assets/app.js').write_text('export const value = 1;', encoding='utf-8')
                self.assertEqual(client.get('/').status_code, 200)
                self.assertEqual(client.get('/assets/app.js').status_code, 200)
                self.assertEqual(client.get('/requirements.txt').status_code, 404)


if __name__ == '__main__':
    unittest.main()
