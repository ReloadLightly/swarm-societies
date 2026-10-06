"""Fixed allocation planner using only a declared, lagged legal observation.

This deliberately approximate local forecast is independent of the simulator.
It assumes unit member productivity, no harvesting of neighbours, no future
investment after the focal allocation, and decay-only external infrastructure.
It samples weather but never reads world snapshots, true laws or future draws.
The known-law reference is supplied coefficients through the same interface.
"""
from __future__ import annotations

from copy import deepcopy
import math

import numpy as np

VERSION = 'allocation-planner-v1'
MENU = (0.0, 0.5, 1.0)
PUBLIC_CONSTANTS = {'rho': .96, 'eta': .125, 'h': 2.4, 'c': .08}
PRIOR_BOUNDS = np.array([[2., 8.], [.5, 3.], [0., .8]])
PACKET_KEYS = {'event_id', 'tick', 'patch', 'phase', 'stock_before', 'capacity',
               'own_infrastructure', 'other_infrastructure', 'growth', 'sensor_sigma'}
OBS_KEYS = {'version', 'tick', 'society_id', 'wealth', 'treasury', 'infrastructure',
            'last_growth', 'consumption_need', 'tax_rate'}


def _number(value, name, lower=0.):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Expected finite number: '+name)
    if lower is not None and value < lower:
        raise ValueError('Out-of-range '+name)
    return float(value)


def observation(institution, last_growth, *, consumption_need=.85, tax_rate=.6):
    """Allowlist a legacy institution payload and one already delivered event.

    Event origin/delivery authentication belongs to the trusted sharing harness.
    This function additionally enforces home identity and a one-tick lag. Current
    growth, stock, tax receipts, productivity and evaluator metadata are absent.
    """
    legal = {'tick', 'society_id', 'n_societies', 'treasury', 'infrastructure',
             'mean_wealth', 'members', 'reports'}
    if set(institution) != legal:
        raise ValueError('Unexpected institution observation fields')
    members = institution['members']
    if (not isinstance(members, list) or len(members) != 4
            or any(not isinstance(member, dict) or set(member) != {'id', 'wealth'}
                   or type(member['id']) is not int or member['id'] != index
                   for index, member in enumerate(members))):
        raise ValueError('Unexpected institution member observation fields or identities')
    if set(last_growth) != PACKET_KEYS:
        raise ValueError('Unexpected growth observation fields')
    packet = deepcopy(last_growth)
    result = {'version': VERSION, 'tick': institution['tick'],
              'society_id': institution['society_id'],
              'wealth': [m['wealth'] for m in institution['members']],
              'treasury': institution['treasury'], 'infrastructure': institution['infrastructure'],
              'last_growth': packet, 'consumption_need': consumption_need, 'tax_rate': tax_rate}
    validate_observation(result)
    return result


def validate_observation(obs):
    if set(obs) != OBS_KEYS or obs['version'] != VERSION:
        raise ValueError('Unexpected planner observation contract')
    for key in ('tick', 'society_id'):
        if type(obs[key]) is not int or obs[key] < 0:
            raise ValueError('Invalid '+key)
    if not isinstance(obs['wealth'], list) or len(obs['wealth']) != 4:
        raise ValueError('This control requires four members')
    for value in obs['wealth']:
        _number(value, 'wealth')
    for key in ('treasury', 'infrastructure', 'consumption_need', 'tax_rate'):
        _number(obs[key], key)
    if obs['tax_rate'] > .8:
        raise ValueError('Tax rate exceeds legal range')
    packet = obs['last_growth']
    if set(packet) != PACKET_KEYS:
        raise ValueError('Unexpected growth fields')
    if (type(packet['tick']) is not int or packet['tick'] != obs['tick']-1 or
            type(packet['patch']) is not int or packet['patch'] != obs['society_id']
            or packet['phase'] != 'before_actions'):
        raise ValueError('Planner requires its last completed home event, never current growth')
    if not isinstance(packet['event_id'], str) or not packet['event_id']:
        raise ValueError('Missing evidence identity')
    for key in ('stock_before', 'capacity', 'own_infrastructure', 'other_infrastructure', 'sensor_sigma'):
        _number(packet[key], key)
    _number(packet['growth'], 'growth', lower=None)
    if packet['capacity'] <= 0 or packet['stock_before'] > packet['capacity']:
        raise ValueError('Stock exceeds capacity')


def forecast(obs, coefficients, *, seed, horizon=32, menu=MENU):
    """Commit forecasts and a choice before any evaluator branch is executed.

    Coefficients are N equally weighted posterior/prior/known-law draws. All
    actions share weather and resolution order within each planning sample.
    Array rows are simulation samples, not independent experimental replicates.
    """
    validate_observation(obs)
    coefficients = np.asarray(coefficients, dtype=float)
    if (coefficients.ndim != 2 or coefficients.shape[1] != 3 or len(coefficients) < 2
            or not np.isfinite(coefficients).all()
            or np.any(coefficients < PRIOR_BOUNDS[:, 0])
            or np.any(coefficients > PRIOR_BOUNDS[:, 1])):
        raise ValueError('Invalid coefficient draws')
    if type(horizon) is not int or horizon < 1:
        raise ValueError('Invalid forecast horizon')
    menu = tuple(menu)
    if (not menu or menu[0] != 0. or tuple(sorted(set(menu))) != menu
            or any(_number(a, 'action') > 1 for a in menu)):
        raise ValueError('Actions must be unique ordered public fractions starting with redistribution')
    n, members = len(coefficients), len(obs['wealth'])
    rng = np.random.default_rng(seed)
    weather = rng.uniform(.85, 1.15, (horizon, n))
    orders = np.argsort(rng.random((horizon, n, members)), axis=2)
    r, b, g = coefficients.T
    rho, eta, h, c = (PUBLIC_CONSTANTS[k] for k in ('rho', 'eta', 'h', 'c'))
    packet = obs['last_growth']
    # Last packet precedes last tick's harvest. Past measured growth is noisy;
    # cap it to feasible stock and subtract the prescribed nominal harvest.
    previous_stock = max(0., min(packet['capacity'], packet['stock_before']+packet['growth'])-members*h)
    path_metrics, action_rows = [], []
    for action in menu:
        wealth = np.broadcast_to(np.asarray(obs['wealth'], dtype=float), (n, members)).copy()
        infrastructure = np.full(n, obs['infrastructure'], dtype=float)
        stock = np.full(n, previous_stock)
        other_infrastructure = packet['other_infrastructure'] * rho
        treasury = np.full(n, obs['treasury'])
        consumed = np.zeros(n)
        initial_budget = None
        invested = np.zeros(n)
        for offset in range(horizon):
            if offset:
                infrastructure *= rho
                other_infrastructure *= rho
            growth = r*weather[offset]+b*infrastructure+g*other_infrastructure
            stock = np.minimum(packet['capacity'], stock+growth)
            wealth -= np.minimum(wealth, c)
            harvest = np.minimum(stock, members*h)
            # Four known home harvest intentions, random order, nominal unit
            # productivity. Unlike equal splitting, this preserves scarcity's
            # distribution over members and its effect on consumption shortfall.
            for rank in range(members):
                member_ids = orders[offset, :, rank]
                amount = np.minimum(stock, h)
                stock -= amount
                wealth[np.arange(n), member_ids] += amount*(1-obs['tax_rate'])
            budget = treasury+harvest*obs['tax_rate']
            fraction = action if offset == 0 else 0.
            investment = budget*fraction
            if offset == 0:
                initial_budget = budget.copy()
                invested = investment.copy()
            infrastructure += investment*eta/members
            wealth += (budget-investment)[:, None]/members
            consumption = np.minimum(wealth, obs['consumption_need'])
            wealth -= consumption
            consumed += consumption.sum(axis=1)
            treasury.fill(0.)
        utility = (consumed+.2*wealth.sum(axis=1))/members
        path_metrics.append(utility)
        action_rows.append({'public_fraction': action, 'utility': float(utility.mean()),
            'utility_mcse': float(utility.std(ddof=1)/np.sqrt(n)),
            'consumption_per_member': float(consumed.mean()/members),
            'shortfall_per_member': float(horizon*obs['consumption_need']-consumed.mean()/members),
            'terminal_wealth_per_member': float(wealth.mean()),
            'initial_budget': float(initial_budget.mean()), 'investment': float(invested.mean())})
    paths = np.asarray(path_metrics)
    best = int(np.argmax(paths.mean(axis=1)))
    paired = []
    for j, action in enumerate(menu):
        difference = paths[j]-paths[0]
        paired.append({'public_fraction': action, 'minus_redistribute': float(difference.mean()),
                       'paired_mcse': float(difference.std(ddof=1)/np.sqrt(n))})
    return {'planner': VERSION, 'horizon': horizon, 'n_samples': n,
            'objective': '(window consumption + 0.2 terminal wealth) / members',
            'action': menu[best], 'actions': action_rows, 'paired': paired,
            'tie_break': 'first maximum in ascending public fraction',
            'assumptions': 'Home-only harvesting; unit productivity; last noisy growth stock reconstruction; decay-only external infrastructure; no subsequent investment.'}
