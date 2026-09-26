import unittest
from datetime import date
from decimal import Decimal as D

from engine import compare, payment_dates


def inputs(**updates):
    value = dict(holdings={'BTC': '10', 'ETH': '0', 'USDC': '0'}, cash='0',
                 income='0', expense='100', payment_day=1, start='2026-01-01',
                 reserve_months=3, fee_percent='0',
                 shocks={'BTC': '0', 'ETH': '0', 'USDC': '0'})
    value.update(updates)
    return value


PRICES = {'BTC': '100', 'ETH': '10', 'USDC': '1'}


class EngineTests(unittest.TestCase):
    def test_constant_price_and_exact_depletion(self):
        a, b = compare(inputs(), PRICES)['strategies']
        for s in (a, b):
            self.assertEqual(s['covered_payments'], 10)
            self.assertEqual(s['failure']['date'], '2026-12-01')
            self.assertEqual(D(s['failure']['shortfall']), 100)
        self.assertEqual(D(a['rows'][-2]['total']), D(b['rows'][-2]['total']))

    def test_drop_and_reserve_before_shock(self):
        a, b = compare(inputs(shocks={'BTC': '-50', 'ETH': '0', 'USDC': '0'}), PRICES)['strategies']
        self.assertEqual(a['covered_payments'], 5)
        self.assertEqual(b['covered_payments'], 6)
        self.assertEqual(D(b['failure']['shortfall']), 50)
        self.assertEqual(D(b['initial_sale']['sold']['BTC']), 3)

    def test_cash_shortfall_and_income_before_payment(self):
        value = inputs(holdings=dict.fromkeys(PRICES, '0'), cash='50', income='50')
        a = compare(value, PRICES)['strategies'][0]
        self.assertEqual(a['covered_payments'], 1)
        self.assertEqual(D(a['failure']['shortfall']), 50)

    def test_fee_is_deducted_and_reserve_unattainable(self):
        a, b = compare(inputs(fee_percent='1', reserve_months=12), PRICES)['strategies']
        for s in (a, b):
            self.assertEqual(s['covered_payments'], 9)
            self.assertAlmostEqual(D(s['failure']['shortfall']), D(10), delta=D('1e-18'))
            self.assertAlmostEqual(D(s['fees']), D(10), delta=D('1e-18'))
        self.assertEqual(D(b['reserve_shortfall']), 210)

    def test_existing_cash_counts_toward_reserve(self):
        b = compare(inputs(cash='300'), PRICES)['strategies'][1]
        self.assertEqual(D(b['initial_sale']['sold']['BTC']), 0)

    def test_usdc_then_proportional_risk_assets(self):
        value = inputs(holdings={'BTC': '1', 'ETH': '10', 'USDC': '50'}, expense='150')
        prices = dict(PRICES, USDC='0.8')
        row = compare(value, prices)['strategies'][0]['rows'][0]
        self.assertEqual(D(row['sold']['USDC']), 50)
        self.assertEqual(D(row['sold']['BTC']), D('0.55'))
        self.assertEqual(D(row['sold']['ETH']), D('5.5'))

    def test_sell_reduces_subsequent_exposure(self):
        # Cover 365 days after the baseline; the price doubles only after the first payment.
        history = [dict.fromkeys(PRICES, '1') for _ in range(366)]
        for p in history[32:]:
            p['BTC'] = '2'
        a = compare(inputs(), PRICES, history)['strategies'][0]
        self.assertEqual(D(a['curve'][32]['total']), 1800)

    def test_zero_price_never_negative_holdings(self):
        result = compare(inputs(shocks=dict.fromkeys(PRICES, '-100')), PRICES)
        a = result['strategies'][0]
        self.assertEqual(a['covered_payments'], 0)
        self.assertEqual(D(a['failure']['shortfall']), 100)
        self.assertTrue(all(D(v) >= 0 for v in a['rows'][0]['holdings'].values()))

    def test_covered_period_not_infinity_and_zero_reserve_equivalence(self):
        a, b = compare(inputs(income='100', reserve_months=0), PRICES)['strategies']
        self.assertEqual(a['covered_payments'], 12)
        self.assertIsNone(a['failure'])
        self.assertEqual(a['curve'], b['curve'])

    def test_month_end_leap_year_and_strict_start(self):
        dates = payment_dates(date(2024, 1, 31), 31)
        self.assertEqual(dates[0], date(2024, 2, 29))
        self.assertEqual(dates[-1], date(2025, 1, 31))
        self.assertEqual(len(dates), 12)

    def test_validation(self):
        for change in [dict(cash='NaN'), dict(income='-1'), dict(expense='0'),
                       dict(fee_percent='100'), dict(payment_day=32), dict(payment_day=1.5),
                       dict(reserve_months=-1), dict(holdings={'BTC': '1'}),
                       dict(shocks=dict.fromkeys(PRICES, '-101'))]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                compare(inputs(**change), PRICES)

    def test_missing_historical_days_rejected(self):
        with self.assertRaises(ValueError):
            compare(inputs(), PRICES, [dict.fromkeys(PRICES, '1')])

    def test_tiny_exponent_cannot_expand_report(self):
        with self.assertRaises(ValueError):
            compare(inputs(cash='1e-10000'), PRICES)

    def test_initial_remaining_units_available_for_exact_export(self):
        b = compare(inputs(), PRICES)['strategies'][1]
        self.assertEqual(D(b['initial_holdings']['BTC']), 7)


if __name__ == '__main__':
    unittest.main()
