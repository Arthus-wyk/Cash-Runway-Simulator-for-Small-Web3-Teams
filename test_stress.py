"""Offline regression tests for price paths and decision summaries."""
import copy
import unittest
from datetime import date
from decimal import Decimal

from engine import compare
from stress import build_path, run_stress, PRESETS
from test_engine import inputs, PRICES


class StressTests(unittest.TestCase):
    def test_calendar_nodes_zero_and_invalid_input(self):
        definition = copy.deepcopy(PRESETS[0])
        definition['nodes'][0]['changes']['BTC'] = '-100'
        path = build_path('2024-01-31', definition)
        self.assertEqual(len(path), 367)
        self.assertEqual(Decimal(path[29]['BTC']), 0)
        self.assertEqual(Decimal(path[0]['BTC']), 1)
        result = compare(inputs(start='2024-01-31'), PRICES, path, hypothetical=True)
        self.assertIn('Hypothetical', ' '.join(result['assumptions']))
        with self.assertRaises(ValueError):
            compare(inputs(start='2024-01-31'), PRICES, path)
        for change in ['NaN', '-101', '1001', True]:
            definition['nodes'][0]['changes']['BTC'] = change
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_path('2024-01-31', definition)

    def test_matrix_matches_detail_and_zero_reserve_baseline(self):
        definitions = [PRESETS[0], PRESETS[1]]
        report = run_stress(inputs(), PRICES, 6, definitions)
        self.assertEqual(len(report['rows']), 13)
        for row in report['rows']:
            for cell, definition in zip(row['cells'], definitions):
                result = compare(inputs(reserve_months=row['reserve_months']), PRICES,
                                 build_path('2026-01-01', definition), hypothetical=True)
                first, second = result['strategies']
                self.assertEqual(cell['covered_payments'], second['covered_payments'])
                self.assertEqual(cell['failure'], second['failure'])
                self.assertEqual(cell['meets_target'], second['covered_payments'] >= 6)
                if row['reserve_months'] == 0:
                    self.assertEqual(first['curve'], second['curve'])

    def test_order_matters_with_equal_end_prices(self):
        outcomes = [compare(inputs(), PRICES, build_path('2026-01-01', item), hypothetical=True)
                    for item in PRESETS[:2]]
        self.assertEqual(outcomes[0]['path'][-1]['prices'], outcomes[1]['path'][-1]['prices'])
        self.assertNotEqual(outcomes[0]['strategies'][0]['covered_payments'],
                            outcomes[1]['strategies'][0]['covered_payments'])

    def test_no_solution_and_terminal_comparison_rules(self):
        poor = inputs(holdings=dict.fromkeys(PRICES, '0'), cash='0')
        report = run_stress(poor, PRICES, 1, [PRESETS[-1]])
        self.assertIsNone(report['minimum_reserve'])
        self.assertTrue(all(row['passed_count'] == 0 for row in report['rows']))
        self.assertIsNone(report['rows'][0]['cells'][0]['terminal_difference'])
        rich = run_stress(inputs(income='100'), PRICES, 12, [PRESETS[-1]])
        self.assertEqual(rich['minimum_reserve'], 0)
        self.assertEqual(Decimal(rich['rows'][0]['cells'][0]['terminal_difference']), 0)
        self.assertLess(Decimal(rich['rows'][3]['cells'][0]['terminal_difference']), 0)

    def test_invalid_selection_target_and_nodes(self):
        for target, definitions in [(0, [PRESETS[0]]), (13, [PRESETS[0]]), (1, []),
                                    (1, [PRESETS[0], PRESETS[0]]), (True, [PRESETS[0]])]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                run_stress(inputs(), PRICES, target, definitions)
        bad = copy.deepcopy(PRESETS[0])
        bad['nodes'][0]['month'] = 2
        with self.assertRaises(ValueError):
            build_path('2026-01-01', bad)


if __name__ == '__main__':
    unittest.main()
