"""Deterministic cash runway simulation using only existing holdings."""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, localcontext

COINS = ('BTC', 'ETH', 'USDC')
ZERO = Decimal(0)
ONE = Decimal(1)
EPSILON = Decimal('1e-18')
RULES = [
    'Simulation, not a forecast: the horizon is 12 calendar months from the start date, with no extrapolation beyond it.',
    'Dates use UTC; the first payment is strictly after the start date; short months use their final day.',
    'USD income arrives before each payment; if cash is insufficient, sell USDC first, then BTC and ETH in proportion to market value.',
    'Strategy B raises cash at current prices to N times monthly expenses; existing cash counts, future income does not, and the reserve is not replenished.',
    'After Strategy B establishes its reserve, the custom shock occurs on day 1; each asset moves once and then stays flat.',
    'Historical simulated price = current quote x historical daily close / historical baseline close; relative days are replayed and trades occur at day end.',
    'Net sale proceeds = units x simulated price x (1 - fee rate); the fee includes all simulated conversion costs with no extra slippage.',
    'USDC uses its market quote while USD cash keeps face value; interest, tax, settlement delay, minimum trade size, and liquidity limits are ignored.',
    'If a payment cannot be completed, pay available cash, record the unpaid shortfall, and stop that strategy without assuming debt or later repayment.',
    'The curve is cash plus the market value of remaining holdings; future liquidation fees are excluded and reserve-building fees are included at the start.',
    'Decimal precision is 40; internal values are not rounded to cents or token units; residuals below USD 1e-18 are zero. Displayed amounts are rounded to cents.',
]


def number(value, label, low=ZERO, high=Decimal('1e15')):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f'{label} must be numeric')
    try:
        if len(str(value)) > 80:
            raise ValueError(f'{label} is too long')
        value = Decimal(str(value))
        if not value.is_finite() or not low <= value <= high:
            raise ValueError(f'{label} must be between {low} and {high}')
        if value and value.adjusted() < -18:
            raise ValueError(f'{label} must be zero or at least 1e-18 in absolute value')
    except InvalidOperation:
        raise ValueError(f'{label} must be a valid number') from None
    return value


def coin_values(values, label, low=ZERO, high=Decimal('1e12')):
    if not isinstance(values, dict) or set(values) != set(COINS):
        raise ValueError(f'{label} must contain BTC, ETH, and USDC')
    return {c: number(values[c], f'{label} {c}', low, high) for c in COINS}


def integer(value, label, low, high):
    n = number(value, label, Decimal(low), Decimal(high))
    if n != n.to_integral_value():
        raise ValueError(f'{label} must be an integer')
    return int(n)


def month_after(start, months):
    year, month = divmod(start.year * 12 + start.month - 1 + months, 12)
    return date(year, month + 1, min(start.day, monthrange(year, month + 1)[1]))


def payment_dates(start, day, months=12):
    end = month_after(start, months)
    dates = []
    for offset in range(months + 1):
        month = month_after(start.replace(day=1), offset)
        payment = month.replace(day=min(day, monthrange(month.year, month.month)[1]))
        if start < payment <= end:
            dates.append(payment)
    return dates


def total(cash, holdings, prices):
    return cash + sum((holdings[c] * prices[c] for c in COINS), ZERO)


def sell(holdings, prices, needed, fee):
    """Update holdings by selling only enough units to raise the required net USD."""
    sold = dict.fromkeys(COINS, ZERO)
    net = ZERO
    fees = ZERO
    for group in [('USDC',), ('BTC', 'ETH')]:
        value = sum((holdings[c] * prices[c] for c in group), ZERO)
        if value <= ZERO or needed - net <= EPSILON:
            continue
        fraction = min(ONE, (needed - net) / (value * (ONE - fee)))
        for c in group:
            units = holdings[c] * fraction
            gross = units * prices[c]
            holdings[c] -= units
            sold[c] += units
            fees += gross * fee
            net += gross * (ONE - fee)
    return {'sold': sold, 'net': net, 'fee': fees}


def strategy(name, initial, cash, income, expense, fee, reserve, start, dates, path):
    holdings = initial.copy()
    target = expense * reserve
    initial_sale = sell(holdings, path[0], max(ZERO, target - cash), fee)
    cash += initial_sale['net']
    reserve_shortfall = max(ZERO, target - cash)
    if reserve_shortfall < EPSILON:
        reserve_shortfall = ZERO
    reserve_cash = cash
    initial_holdings = holdings.copy()
    fees = initial_sale['fee']
    rows, curve = [], []
    failure = None
    covered = 0
    payment_set = set(dates)
    for offset, prices in enumerate(path):
        day = start + timedelta(days=offset)
        if day in payment_set:
            cash_before = cash
            cash += income
            sale = sell(holdings, prices, max(ZERO, expense - cash), fee)
            cash += sale['net']
            fees += sale['fee']
            shortfall = max(ZERO, expense - cash)
            if shortfall < EPSILON:
                shortfall = ZERO
            paid = expense - shortfall
            cash = max(ZERO, cash - paid)
            rows.append(dict(date=day.isoformat(), cash_before=cash_before, income=income,
                             expense=expense, paid=paid, shortfall=shortfall,
                             sold=sale['sold'], sale_net=sale['net'], fee=sale['fee'],
                             cash=cash, holdings=holdings.copy(), prices=prices.copy(),
                             total=total(cash, holdings, prices)))
            if shortfall:
                failure = {'date': day.isoformat(), 'shortfall': shortfall}
            else:
                covered += 1
        curve.append({'date': day.isoformat(), 'total': total(cash, holdings, prices), 'cash': cash})
        if failure:
            break
    return dict(name=name, covered_payments=covered, failure=failure, rows=rows, curve=curve,
                initial_sale=initial_sale, initial_holdings=initial_holdings, reserve_target=target, reserve_cash=reserve_cash,
                reserve_shortfall=reserve_shortfall, fees=fees)


def serializable(value):
    if isinstance(value, Decimal):
        return format(value.normalize(), 'f')
    if isinstance(value, dict):
        return {k: serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serializable(v) for v in value]
    return value


def compare(inputs, prices, history=None, *, hypothetical=False):
    with localcontext() as context:
        context.prec = 40
        if not isinstance(inputs, dict):
            raise ValueError('Input must be an object')
        initial = coin_values(inputs.get('holdings'), 'Holdings')
        prices = coin_values(prices, 'Prices', Decimal('1e-18'))
        cash = number(inputs.get('cash'), 'USD cash')
        income = number(inputs.get('income'), 'Monthly income')
        expense = number(inputs.get('expense'), 'Monthly expenses', Decimal('0.01'))
        fee = number(inputs.get('fee_percent'), 'Fee rate', ZERO, Decimal(20)) / 100
        reserve = integer(inputs.get('reserve_months'), 'Cash reserve months', 0, 12)
        day = integer(inputs.get('payment_day'), 'Payment day', 1, 31)
        try:
            start = date.fromisoformat(inputs['start'])
            if not 2000 <= start.year <= 2100:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise ValueError('Start date must be between 2000 and 2100') from None
        end = month_after(start, 12)
        days = (end - start).days
        dates = payment_dates(start, day)
        if history is None:
            shocks = coin_values(inputs.get('shocks'), 'Price change', Decimal(-100), Decimal(1000))
            shocked = {c: prices[c] * (ONE + shocks[c] / 100) for c in COINS}
            path = [prices] + [shocked] * days
        else:
            if not isinstance(history, list) or len(history) < days + 1:
                raise ValueError('Historical data does not cover the full simulation period; this scenario is unavailable')
            ratios = [coin_values(p, 'Relative path price', ZERO if hypothetical else Decimal('1e-18')) for p in history[:days + 1]]
            if any(ratios[0][c] != ONE for c in COINS):
                raise ValueError('The relative price on the historical baseline date must equal 1')
            path = [{c: prices[c] * ratios[i][c] for c in COINS} for i in range(days + 1)]
        assumptions = [rule for index, rule in enumerate(RULES) if index not in (4, 5)]
        assumptions.append('Hypothetical path: node changes are relative to the starting quote and linearly interpolated over calendar days; this is neither historical data nor a forecast.'
                           if hypothetical else RULES[4 if history is None else 5])
        result = dict(start=start.isoformat(), end=end.isoformat(), payment_dates=[d.isoformat() for d in dates],
                      initial_total=total(cash, initial, prices),
                      allocation={**{c: initial[c] * prices[c] for c in COINS}, 'USD': cash},
                      assumptions=assumptions, path=[dict(date=(start + timedelta(days=i)).isoformat(), prices=p)
                                               for i, p in enumerate(path)],
                      strategies=[strategy(name, initial, cash, income, expense, fee, n, start, dates, path)
                                  for name, n in [('A', 0), ('B', reserve)]])
        return serializable(result)
