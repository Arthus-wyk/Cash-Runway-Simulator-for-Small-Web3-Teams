"""Hypothetical price paths, reserve matrices, and auditable decision summaries."""
import re
from datetime import date
from decimal import Decimal, localcontext

from engine import COINS, coin_values, compare, integer, month_after, serializable

MONTHS = (1, 3, 6, 12)
PATH_RULE = 'Hypothetical scenario: node changes are relative to the starting quote and linearly interpolated over calendar days, not compounded segment by segment.'
LIMITATION = 'The share of scenarios meeting the target is not a success probability; results apply only to the selected assumptions and do not guarantee future payment capacity.'


def make_preset(identifier, label, btc, eth, usdc):
    """Define four nodes per asset without treating the stablecoin as USD cash."""
    return {'id': identifier, 'label': label, 'kind': 'hypothetical', 'nodes': [
        {'month': month, 'changes': dict(zip(COINS, map(str, values)))}
        for month, values in zip(MONTHS, zip(btc, eth, usdc))]}


PRESETS = [
    make_preset('fall-recover', 'Fall then recover', [-45, -60, -25, 0], [-55, -70, -35, 0], [0, 0, 0, 0]),
    make_preset('rise-fall', 'Rise then fall', [45, 60, 25, 0], [55, 70, 35, 0], [0, 0, 0, 0]),
    make_preset('decline', 'Continued decline', [-10, -25, -40, -60], [-15, -35, -55, -75], [0, 0, 0, 0]),
    make_preset('depeg', 'Stablecoin depeg', [0, 0, 0, 0], [0, 0, 0, 0], [-15, -10, -5, 0]),
    make_preset('growth', 'Continued growth', [10, 25, 40, 60], [15, 35, 55, 80], [0, 0, 0, 0]),
]


def build_path(start, definition):
    """Validate four calendar-month nodes and calculate daily ratios from baseline."""
    if not isinstance(definition, dict):
        raise ValueError('Scenario must be an object')
    identifier, label = definition.get('id'), definition.get('label')
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', identifier):
        raise ValueError('Scenario ID is invalid')
    if not isinstance(label, str) or not label.strip() or len(label) > 60 or any(ord(c) < 32 for c in label):
        raise ValueError('Scenario name must contain 1 to 60 visible characters')
    try:
        start = date.fromisoformat(start)
    except (TypeError, ValueError):
        raise ValueError('Start date is invalid') from None
    if not 2000 <= start.year <= 2100:
        raise ValueError('Start date must be between 2000 and 2100')
    nodes = definition.get('nodes')
    if not isinstance(nodes, list) or len(nodes) != 4:
        raise ValueError('Four nodes are required at months 1, 3, 6, and 12')
    with localcontext() as context:
        context.prec = 40
        points = [(0, dict.fromkeys(COINS, Decimal(1)))]
        for month, node in zip(MONTHS, nodes):
            if not isinstance(node, dict) or isinstance(node.get('month'), bool) or node.get('month') != month:
                raise ValueError('Node months must be 1, 3, 6, and 12 in order')
            changes = coin_values(node.get('changes'), 'Node price change', Decimal(-100), Decimal(1000))
            points.append(((month_after(start, month) - start).days,
                           {coin: 1 + changes[coin] / 100 for coin in COINS}))
        path = [points[0][1]]
        for (left, first), (right, last) in zip(points, points[1:]):
            for day in range(left + 1, right + 1):
                fraction = Decimal(day - left) / (right - left)
                path.append({coin: first[coin] + (last[coin] - first[coin]) * fraction for coin in COINS})
        return serializable(path)


def run_stress(inputs, prices, target, definitions):
    """Evaluate 13 reserve levels using the same rules as a single simulation."""
    target = integer(target, 'Target payment count', 1, 12)
    if not isinstance(inputs, dict):
        raise ValueError('Input must be an object')
    if not isinstance(definitions, list) or not 1 <= len(definitions) <= 5:
        raise ValueError('Select between 1 and 5 hypothetical scenarios')
    paths = [build_path(inputs.get('start'), item) for item in definitions]
    if len({item['id'] for item in definitions}) != len(definitions):
        raise ValueError('Scenario IDs must be unique')
    rows = []
    with localcontext() as context:
        context.prec = 40
        for reserve in range(13):
            cells = []
            for definition, path in zip(definitions, paths):
                result = compare({**inputs, 'reserve_months': reserve}, prices, path, hypothetical=True)
                baseline, candidate = result['strategies']
                complete = baseline['failure'] is None and candidate['failure'] is None
                difference = (Decimal(candidate['curve'][-1]['total']) - Decimal(baseline['curve'][-1]['total'])) if complete else None
                cells.append({
                    'scenario_id': definition['id'], 'label': definition['label'],
                    'covered_payments': candidate['covered_payments'], 'meets_target': candidate['covered_payments'] >= target,
                    'failure': candidate['failure'], 'fees': candidate['fees'],
                    'terminal_difference': serializable(difference), 'comparison_date': result['end'] if complete else None,
                    'comparison_note': 'Strategy B minus Strategy A at the same end date; positive means B has more and negative means B has less.' if complete else 'Not applicable: at least one strategy did not reach the end of the simulation.',
                })
            failures = [{**cell['failure'], 'scenario_id': cell['scenario_id'], 'label': cell['label']}
                        for cell in cells if cell['failure']]
            rows.append({
                'reserve_months': reserve, 'cells': cells,
                'passed_count': sum(cell['meets_target'] for cell in cells),
                'all_passed': all(cell['meets_target'] for cell in cells),
                'fully_funded': Decimal(candidate['reserve_shortfall']) == 0,
                'reserve_target': candidate['reserve_target'], 'reserve_cash': candidate['reserve_cash'],
                'reserve_shortfall': candidate['reserve_shortfall'], 'initial_sale': candidate['initial_sale'],
                'earliest_failure': min(failures, key=lambda failure: failure['date']) if failures else None,
            })
        minimum = next((row['reserve_months'] for row in rows if row['all_passed'] and row['fully_funded']), None)
        return {'target_payments': target, 'minimum_reserve': minimum, 'rows': rows,
                'scenarios': [{**item, 'kind': 'hypothetical', 'daily_ratios': path} for item, path in zip(definitions, paths)],
                'assumptions': result['assumptions'], 'path_rule': PATH_RULE, 'limitation': LIMITATION,
                'start': result['start'], 'end': result['end'], 'payment_dates': result['payment_dates']}
