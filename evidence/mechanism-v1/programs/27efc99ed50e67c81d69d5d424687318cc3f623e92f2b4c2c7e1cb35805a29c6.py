"""Initial members harvest locally; a modest fixed tax funds infrastructure."""
# EVOLVE-BLOCK-START
def clamp(value, lower, upper):
    return min(upper, max(lower, value))
def liquidity_value(resources):
    resources = max(0.0, resources)
    return (
        0.20 * resources
        + 0.80 * min(0.85, resources)
        + 0.30 * min(1.70, max(0.0, resources - 0.85))
        + 0.10 * min(2.55, max(0.0, resources - 2.55))
    )
def member_signals(observation, passive):
    broadcast = observation.get('messages', {}) or {}
    key = str(observation['member_id'])
    payments = broadcast.get(
        'payments', broadcast.get('rebates', {})
    ) or {}
    rebate = max(0.0, payments.get(key, passive))
    passive_payments = broadcast.get('passive_rebates', {}) or {}
    tax_returns = broadcast.get('tax_returns', {}) or {}
    marginal_return = 0.0
    transfer = rebate
    if key in passive_payments and key in tax_returns:
        transfer = max(0.0, passive_payments[key])
        marginal_return = clamp(tax_returns[key], 0.0, 1.0)
    return {
        'loads': broadcast.get('loads', {}) or {},
        'rebate': rebate,
        'quoted': key in payments,
        'transfer': transfer,
        'tax_return': marginal_return,
        'raids': broadcast.get(
            'raid_permission', broadcast.get('raids', True)
        )
    }
def update_return_model(observation, state, passive):
    models = state.get('models', {}).copy()
    previous = state.get('previous', {})
    wealth = max(0.0, observation['wealth'])
    tick = observation['tick']
    if not previous or wealth <= 0.001:
        return models, passive
    receipt = (
        wealth - previous['wealth']
        + 0.85 + previous['cost']
    )
    action = previous['action']
    certain_harvest = (
        action == 'harvest'
        and previous['stock'] >= (
            2.76
            * max(1, observation['n_members'])
            * max(1, observation['n_societies'])
        )
    )
    if not previous['quoted']:
        if action == 'rest' or certain_harvest:
            direct = 0.0
            if certain_harvest:
                direct = previous['maximum'] * (1.0 - previous['tax'])
            observed_passive = clamp(receipt - direct, 0.0, 4.0)
            passive = 0.75 * passive + 0.25 * observed_passive
    maximum = previous.get('maximum', 0.0)
    key = previous.get('key', '')
    if maximum <= 0.0001 or not key:
        return models, passive
    received = max(0.0, receipt - previous['rebate'])
    if action == 'harvest':
        received /= max(0.20, 1.0 - previous['tax'])
    fraction = clamp(received / maximum, 0.0, 1.0)
    full_mass = max(0.0, 2.0 * fraction - 1.0)
    half_mass = 2.0 * min(fraction, 1.0 - fraction)
    row = models.get(key, [0.0, 0.0, 0.0, tick])
    age = max(1, tick - row[3])
    discount = 1.0 / (1.0 + 0.08 * age)
    weight = 0.85 if previous['quoted'] else 0.60
    models[key] = [
        discount * row[0] + weight,
        discount * row[1] + weight * full_mass,
        discount * row[2] + weight * half_mass,
        tick
    ]
    return models, passive
def outcome_distribution(models, key, tick, mean, half_mass):
    row = models.get(key, [0.0, 0.0, 0.0, tick])
    age = max(0, tick - row[3])
    discount = 1.0 / (1.0 + 0.05 * age)
    samples = discount * row[0]
    prior_full = max(0.0, mean - 0.5 * half_mass)
    denominator = 2.0 + samples
    full = (2.0 * prior_full + discount * row[1]) / denominator
    half = (2.0 * half_mass + discount * row[2]) / denominator
    return full, half, samples
def action_menu(observation, state, models, signals):
    tick = observation['tick']
    society = observation['society_id']
    capacity = 2.4 * observation['productivity']
    members = max(1, observation['n_members'])
    societies = max(1, observation['n_societies'])
    previous = state.get('previous', {})
    loads = signals['loads']
    offers = [{
        'action': 'rest',
        'target': society,
        'effort': 0.0,
        'maximum': 0.0,
        'stock': 0.0,
        'key': '',
        'full': 0.0,
        'half': 0.0,
        'samples': 0.0
    }]
    for patch in observation['patches']:
        stock = max(0.0, patch['stock'])
        if stock <= 0.0001:
            continue
        target = patch['id']
        maximum = min(capacity, stock)
        effort = maximum / max(0.01, capacity)
        competitors = (
            1.0 + 0.5 * max(0, members - 1)
            + 0.5 * max(0, societies - 1)
        )
        patch_key = str(target)
        if patch_key in loads:
            allied_load = max(0.0, loads[patch_key])
            if (
                previous.get('action') == 'harvest'
                and previous.get('target') == target
            ):
                allied_load = max(
                    0.0,
                    allied_load - previous.get('maximum', capacity)
                )
            external = 0.5 * members * (societies - 1) / societies
            competitors = (
                1.0 + external
                + 0.65 * allied_load / max(0.1, capacity)
            )
        prior = clamp(
            stock / max(0.01, competitors * maximum), 0.0, 1.0
        )
        relative_stock = stock / max(0.01, capacity)
        bucket = 0
        for boundary in [1.0, 2.5, 5.0]:
            if relative_stock >= boundary:
                bucket += 1
        key = 'h:' + patch_key + ':' + str(bucket)
        prior_half = 0.50 * min(prior, 1.0 - prior)
        full, half, samples = outcome_distribution(
            models, key, tick, prior, prior_half
        )
        offers.append({
            'action': 'harvest',
            'target': target,
            'effort': effort,
            'maximum': maximum,
            'stock': stock,
            'key': key,
            'full': full,
            'half': half,
            'samples': samples
        })
    if signals['raids']:
        for offset in range(1, societies):
            target = (society + offset) % societies
            key = 'r:' + str(target)
            full, half, samples = outcome_distribution(
                models, key, tick, 0.57, 0.14
            )
            offers.append({
                'action': 'raid',
                'target': target,
                'effort': 1.0,
                'maximum': 1.656,
                'stock': 0.0,
                'key': key,
                'full': full,
                'half': half,
                'samples': samples
            })
    return offers
def select_action(observation, offers, signals):
    wealth = max(0.0, observation['wealth'])
    tax = clamp(observation['tax_rate'], 0.0, 0.8)
    transfer = signals['transfer']
    baseline = liquidity_value(wealth + transfer)
    chosen = offers[0]
    best_score = 0.0
    for index, offer in enumerate(offers):
        if offer['action'] == 'rest':
            continue
        maximum = offer['maximum']
        if offer['action'] == 'harvest':
            maximum *= 1.0 - tax * (1.0 - signals['tax_return'])
        cost = min(wealth, 0.08 * offer['effort'])
        starting = max(0.0, wealth - cost) + transfer
        full = offer['full']
        half = offer['half']
        empty = max(0.0, 1.0 - full - half)
        score = (
            empty * liquidity_value(starting)
            + half * liquidity_value(starting + 0.5 * maximum)
            + full * liquidity_value(starting + maximum)
            - baseline
        )
        if wealth >= 1.70:
            score += 0.004 * maximum / (1.0 + offer['samples'])
        score += 0.00003 * min(30.0, offer['stock'])
        score += 0.000001 * (
            (observation['tick'] + observation['member_id'] + index)
            % max(1, len(offers))
        )
        if score > best_score:
            best_score = score
            chosen = offer
    return chosen
def member_policy(observation, private_state):
    state = private_state or {}
    wealth = max(0.0, observation['wealth'])
    capacity = 2.4 * observation['productivity']
    tax = clamp(observation['tax_rate'], 0.0, 0.8)
    passive = max(
        0.0, state.get('passive', 0.35 * tax * capacity)
    )
    models, passive = update_return_model(observation, state, passive)
    signals = member_signals(observation, passive)
    offers = action_menu(observation, state, models, signals)
    chosen = select_action(observation, offers, signals)
    patch_report = []
    richest_patch = observation['society_id']
    richest_stock = 0.0
    for patch in observation['patches']:
        stock = max(0.0, patch['stock'])
        patch_report.append([patch['id'], round(stock, 3)])
        if stock > richest_stock:
            richest_patch = patch['id']
            richest_stock = stock
    expected = chosen['maximum'] * (
        chosen['full'] + 0.5 * chosen['half']
    )
    return {
        'action': chosen['action'],
        'target': chosen['target'],
        'effort': chosen['effort'],
        'message': {
            'protocol': 'waterline_1',
            'patches': patch_report,
            'patch': richest_patch,
            'stock': round(richest_stock, 3),
            'action': chosen['action'],
            'target': chosen['target'],
            'effort': round(chosen['effort'], 4),
            'capacity': round(capacity, 4),
            'yield': round(expected, 4)
        },
        'state': {
            'models': models,
            'passive': passive,
            'previous': {
                'action': chosen['action'],
                'target': chosen['target'],
                'wealth': wealth,
                'cost': min(wealth, 0.08 * chosen['effort']),
                'tax': tax,
                'maximum': chosen['maximum'],
                'stock': chosen['stock'],
                'key': chosen['key'],
                'rebate': signals['rebate'],
                'quoted': signals['quoted']
            }
        }
    }
def collect_reports(observation):
    reports = {}
    stocks = {}
    loads = {}
    for report in observation.get('reports', []):
        message = report.get('message', {}) or {}
        reports[str(report['member'])] = message
        for patch in message.get('patches', []):
            key = str(patch[0])
            stocks[key] = max(
                stocks.get(key, 0.0), max(0.0, patch[1])
            )
        if 'patch' in message and 'stock' in message:
            key = str(message['patch'])
            stocks[key] = max(
                stocks.get(key, 0.0), max(0.0, message['stock'])
            )
        action = message.get('action', 'harvest')
        target = message.get('target', message.get('patch'))
        if action == 'harvest' and target is not None:
            key = str(target)
            capacity = clamp(message.get('capacity', 2.4), 0.1, 2.76)
            effort = clamp(message.get('effort', 1.0), 0.0, 1.0)
            loads[key] = loads.get(key, 0.0) + capacity * effort
    return reports, stocks, loads
def waterfill(holdings, budget):
    count = len(holdings)
    if count == 0:
        return []
    ordered = sorted([
        [holdings[index], index] for index in range(count)
    ])
    remaining = max(0.0, budget)
    level = ordered[0][0]
    for rank in range(1, count):
        price = rank * max(0.0, ordered[rank][0] - level)
        if remaining <= price:
            level += remaining / rank
            remaining = 0.0
            break
        remaining -= price
        level = ordered[rank][0]
    if remaining > 0.0:
        level += remaining / count
    return [max(0.0, level - holding) for holding in holdings]
def update_ledger(observation, state, stocks):
    members = observation['members']
    count = len(members)
    wealths = [max(0.0, member['wealth']) for member in members]
    infrastructure = max(0.0, observation['infrastructure'])
    liquid = max(0.0, observation['treasury']) + sum(wealths)
    income = state.get('income', 2.1 * count)
    noise = state.get('noise', 0.30 * count)
    if 'liquid' in state:
        construction = max(
            0.0,
            8.0 * count * (
                infrastructure
                - 0.96 * state.get('infrastructure', infrastructure)
            )
        )
        measured = clamp(
            liquid - state['liquid'] + 0.93 * count + construction,
            0.0, 3.2 * count
        )
        noise = 0.75 * noise + 0.25 * abs(measured - income)
        rate = 0.50 if measured < 0.80 * income else 0.25
        income = (1.0 - rate) * income + rate * measured
    pressure = state.get('pressure', 0.0)
    if stocks:
        ordered = sorted(stocks.values())
        median = ordered[len(ordered) // 2]
        observed = clamp(
            1.0 - median / max(1.0, 2.4 * count), 0.0, 1.0
        )
        pressure = 0.40 * pressure + 0.60 * observed
    deficit = min(
        4.0 * count,
        0.85 * state.get('deficit', 0.0)
        + max(0.0, 0.93 * count - income)
    )
    old_claims = state.get('claims', {})
    claims = {}
    for index, member in enumerate(members):
        key = str(member['id'])
        claims[key] = min(
            4.0,
            0.85 * old_claims.get(key, 0.0)
            + max(0.0, 1.10 - wealths[index])
        )
    return {
        'liquid': liquid,
        'infrastructure': infrastructure,
        'income': income,
        'noise': noise,
        'pressure': pressure,
        'deficit': deficit,
        'claims': claims,
        'tax': state.get('tax', 0.0)
    }
def forecast_flows(observation, reports, stocks, loads, ledger):
    count = len(observation['members'])
    fallback = clamp(
        (ledger['income'] - 0.25 * ledger['noise']) / count,
        0.15, 2.4
    )
    forecasts = []
    contributions = 0.0
    for member in observation['members']:
        message = reports.get(str(member['id']), {})
        action = message.get('action', 'harvest')
        capacity = clamp(message.get('capacity', 2.4), 0.1, 2.76)
        effort = clamp(message.get('effort', 1.0), 0.0, 1.0)
        wealth = max(0.0, member['wealth'])
        cost = min(wealth, 0.08 * effort)
        harvest = 0.0
        other = 0.0
        certainty = 0.55
        if action == 'harvest':
            key = str(message.get('target', message.get('patch')))
            stock = stocks.get(key)
            estimate = fallback
            if stock is not None:
                allied = max(
                    0.0, loads.get(key, 0.0) - capacity * effort
                )
                congestion = 2.0 + 0.50 * allied / max(0.1, capacity)
                estimate = min(capacity * effort, stock / congestion)
                certainty = 0.40 + 0.50 * clamp(
                    stock / max(0.1, 4.0 * capacity), 0.0, 1.0
                )
            if 'yield' in message:
                estimate = (
                    0.5 * estimate
                    + 0.5 * clamp(message['yield'], 0.0, capacity * effort)
                )
            harvest = min(
                capacity * effort,
                max(0.0, 0.35 * fallback + 0.65 * estimate)
            )
        elif action == 'raid':
            other = 0.40 * clamp(message.get('yield', 0.85), 0.0, 1.656)
        elif action == 'contribute':
            contribution = min(
                max(0.0, wealth - cost - 2.55), 2.0 * effort
            )
            contributions += contribution
            other = -contribution
        elif action == 'share':
            other = -min(max(0.0, wealth - cost), 2.0 * effort)
        elif action == 'rest':
            cost = 0.0
        forecasts.append({
            'harvest': harvest,
            'other': other,
            'cost': cost,
            'certainty': certainty
        })
    return forecasts, contributions
def allocate_budget(observation, forecasts, contributions, ledger):
    members = observation['members']
    count = len(members)
    treasury = max(0.0, observation['treasury'])
    wealths = [max(0.0, member['wealth']) for member in members]
    claims = [ledger['claims'][str(member['id'])] for member in members]
    pressure = ledger['pressure']
    infrastructure = ledger['infrastructure']
    cautious_income = max(0.0, ledger['income'] - 0.35 * ledger['noise'])
    surplus = max(0.0, ledger['liquid'] - count * (2.4 + pressure))
    target = (
        0.70 + 0.80 * pressure
        + min(0.50, ledger['deficit'] / (2.0 * count))
    )
    construction = max(
        0.0,
        8.0 * count * (
            0.04 * infrastructure + 0.12 * (target - infrastructure)
        )
    )
    construction = min(
        construction,
        0.12 * surplus,
        max(
            0.0,
            0.45 * (cautious_income - 0.93 * count) + 0.03 * surplus
        )
    )
    reserve_goal = min(0.40 * count, 0.06 * surplus)
    harvest_total = sum(row['harvest'] for row in forecasts)
    best_loss = 1000000000.0
    selected = {}
    for tax in [0.0, 0.08, 0.16, 0.24, 0.32, 0.40, 0.48, 0.56, 0.64, 0.72]:
        pool = max(0.0, treasury + contributions + tax * harvest_total)
        holdings = []
        essential_gap = 0.0
        buffer_gap = 0.0
        for index, row in enumerate(forecasts):
            holding = max(
                0.0,
                wealths[index] - row['cost'] + row['other']
                + row['certainty'] * (1.0 - tax) * row['harvest']
            )
            holdings.append(holding)
            essential_gap += max(0.0, 0.90 - holding)
            buffer_gap += max(
                0.0, 1.70 + 0.12 * claims[index] - holding
            )
        loss = (
            8.0 * max(0.0, essential_gap - pool)
            + 1.2 * max(0.0, buffer_gap - pool)
            + 0.25 * max(
                0.0, buffer_gap + construction + reserve_goal - pool
            )
            + 0.08 * tax * harvest_total
            + 0.02 * tax
            + 0.025 * abs(tax - ledger['tax'])
        )
        if loss < best_loss:
            best_loss = loss
            selected = {
                'tax': tax,
                'pool': pool,
                'holdings': holdings,
                'buffer_gap': buffer_gap
            }
    pool = selected['pool']
    investment = min(
        construction,
        0.40 * pool,
        max(0.0, pool - selected['buffer_gap'])
    )
    reserve = min(
        reserve_goal,
        max(0.0, pool - selected['buffer_gap'] - investment)
    )
    budget = max(0.0, pool - investment - reserve)
    priorities = [
        selected['holdings'][index] - min(0.24, 0.06 * claims[index])
        for index in range(count)
    ]
    weights = waterfill(priorities, budget)
    if sum(weights) <= 0.000001:
        weights = [
            (1.0 + 0.10 * claims[index])
            / (0.30 + selected['holdings'][index])
            for index in range(count)
        ]
    selected['weights'] = weights
    selected['budget'] = budget
    selected['public'] = investment / pool if pool > 0.000001 else 0.0
    selected['reserve'] = reserve / pool if pool > 0.000001 else 0.0
    return selected
def institution(observation, shared_state):
    state = shared_state or {}
    members = observation['members']
    if not members:
        return {
            'tax_rate': 0.0,
            'public_fraction': 0.0,
            'defense_fraction': 0.0,
            'reserve_fraction': 1.0,
            'redistribution': [],
            'raid_permission': True,
            'messages': {},
            'state': {}
        }
    reports, stocks, loads = collect_reports(observation)
    ledger = update_ledger(observation, state, stocks)
    forecasts, contributions = forecast_flows(
        observation, reports, stocks, loads, ledger
    )
    plan = allocate_budget(observation, forecasts, contributions, ledger)
    ledger['tax'] = plan['tax']
    weight_total = sum(plan['weights'])
    distribution_fraction = max(
        0.0, 1.0 - plan['public'] - plan['reserve']
    )
    rebates = {}
    passive_rebates = {}
    tax_returns = {}
    for index, member in enumerate(members):
        key = str(member['id'])
        weight_share = plan['weights'][index] / weight_total
        rebate = plan['budget'] * weight_share
        marginal = distribution_fraction * weight_share
        own_tax_rebate = (
            marginal * plan['tax'] * forecasts[index]['harvest']
        )
        rebates[key] = round(rebate, 4)
        passive_rebates[key] = round(max(0.0, rebate - own_tax_rebate), 4)
        tax_returns[key] = round(marginal, 5)
    return {
        'tax_rate': plan['tax'],
        'public_fraction': plan['public'],
        'defense_fraction': 0.0,
        'reserve_fraction': plan['reserve'],
        'redistribution': plan['weights'],
        'raid_permission': True,
        'messages': {
            'protocol': 'waterline_1',
            'planner': 'adaptive_flow',
            'loads': loads,
            'rebates': rebates,
            'passive_rebates': passive_rebates,
            'tax_returns': tax_returns,
            'raids': True
        },
        'state': ledger
    }
# EVOLVE-BLOCK-END
