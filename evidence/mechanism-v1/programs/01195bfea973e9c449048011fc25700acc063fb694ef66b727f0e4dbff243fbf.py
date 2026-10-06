"""Initial members harvest locally; a modest fixed tax funds infrastructure."""
# EVOLVE-BLOCK-START
def bounded(value, lower, upper):
    return min(upper, max(lower, value))
def continuation_value(values, wealth):
    position = max(0.0, wealth) / 0.6
    index = int(position)
    if index >= len(values) - 1:
        return values[-1] + 0.2 * (wealth - 0.6 * (len(values) - 1))
    fraction = position - index
    return values[index] * (1.0 - fraction) + values[index + 1] * fraction
def consumption_return(wealth, offer, transfer, values):
    available = max(0.0, wealth - min(wealth, offer['cost'])) + transfer
    result = 0.0
    for probability, income in offer['outcomes']:
        resources = max(0.0, available + income)
        consumption = min(0.85, resources)
        result += probability * (
            consumption + continuation_value(values, resources - consumption)
        )
    return result
def update_member_models(observation, state):
    crowds = state.get('crowds', {}).copy()
    raids = state.get('raids', {}).copy()
    passive = max(0.0, state.get(
        'passive',
        0.25 * observation['tax_rate'] * 2.4 * observation['productivity']
    ))
    previous = state.get('previous', {})
    if not previous:
        return crowds, raids, passive
    wealth = max(0.0, observation['wealth'])
    tick = observation['tick']
    receipt = wealth - previous['wealth'] + 0.85 + previous['cost']
    exact = wealth > 0.00001
    action = previous['action']
    certain = (
        action == 'harvest'
        and previous['stock'] >= (
            2.76 * observation['n_members'] * observation['n_societies']
        )
    )
    if exact and not previous['quoted'] and (certain or action == 'rest'):
        direct = 0.0
        if certain:
            direct = previous['maximum'] * (1.0 - previous['tax'])
        estimate = bounded(receipt - direct, 0.0, 4.0)
        passive = 0.8 * passive + 0.2 * estimate
    received = max(0.0, receipt - previous['transfer'])
    reliability = 0.8 if previous['quoted'] else 0.4
    if action == 'harvest':
        observed = bounded(
            received / max(0.2, previous['retention']),
            0.0,
            previous['maximum']
        )
        predicted = previous['gross']
        error = predicted - observed
        if not exact:
            error = max(0.0, error)
            reliability *= 0.5
        key = str(previous['target'])
        row = crowds.get(key, [1.0, 0.0, tick])
        factor = row[0] * bounded(
            1.0 + reliability * error / max(0.3, previous['capacity']),
            0.7,
            1.3
        )
        crowds[key] = [
            bounded(factor, 0.35, 2.8),
            min(40.0, row[1] + reliability),
            tick
        ]
    elif action == 'raid':
        observed = bounded(received, 0.0, 1.656)
        informative = exact or observed < 0.15
        if informative:
            key = str(previous['target'])
            row = raids.get(key, [0.0, 0.0, 0.0, tick])
            discount = 1.0 / (1.0 + 0.045 * max(1, tick - row[3]))
            success = 1.0 if observed > 0.18 else 0.0
            raids[key] = [
                discount * row[0] + reliability,
                discount * row[1] + reliability * success,
                discount * row[2] + reliability * success * observed,
                tick
            ]
    return crowds, raids, passive
def member_policy(observation, private_state):
    state = private_state or {}
    tick = observation['tick']
    society = observation['society_id']
    member = observation['member_id']
    count = max(1, observation['n_members'])
    societies = max(1, observation['n_societies'])
    wealth = max(0.0, observation['wealth'])
    capacity = 2.4 * observation['productivity']
    tax = bounded(observation['tax_rate'], 0.0, 0.8)
    broadcast = observation.get('messages', {}) or {}
    patches = observation['patches']
    previous = state.get('previous', {})
    crowds, raids, passive = update_member_models(observation, state)
    payments = broadcast.get(
        'rebates', broadcast.get('payments', {})
    ) or {}
    passive_payments = broadcast.get('passive_rebates', {}) or {}
    tax_returns = broadcast.get('tax_returns', {}) or {}
    loads = broadcast.get('loads', {}) or {}
    key = str(member)
    quoted = key in payments
    transfer = max(0.0, payments.get(key, passive))
    marginal = 0.0
    if key in passive_payments and key in tax_returns:
        transfer = max(0.0, passive_payments[key])
        marginal = bounded(tax_returns[key], 0.0, 1.0)
    elif quoted:
        total_payments = sum(max(0.0, value) for value in payments.values())
        marginal = bounded(
            0.85 * transfer / max(0.001, total_payments), 0.0, 0.9
        )
        forecast = capacity
        if previous:
            forecast = 0.0
            if previous.get('action') == 'harvest':
                forecast = (
                    0.6 * previous.get('gross', capacity) + 0.4 * capacity
                )
        transfer = max(0.0, transfer - marginal * tax * forecast)
    retention = 1.0 - tax * (1.0 - marginal)
    offers = [{
        'action': 'rest',
        'target': society,
        'effort': 0.0,
        'cost': 0.0,
        'outcomes': [[1.0, 0.0]],
        'gross': 0.0,
        'maximum': 0.0,
        'stock': 0.0,
        'samples': 0.0
    }]
    average_stock = sum(max(0.0, p['stock']) for p in patches)
    average_stock /= max(1, len(patches))
    for patch in patches:
        stock = max(0.0, patch['stock'])
        if stock <= 0.00001:
            continue
        target = patch['id']
        patch_key = str(target)
        maximum = min(capacity, stock)
        effort = maximum / max(0.01, capacity)
        rivals = max(0.5, count - 1.0)
        if patch_key in loads:
            allied = max(0.0, loads[patch_key])
            if (
                previous.get('action') == 'harvest'
                and previous.get('target') == target
            ):
                allied = max(0.0, allied - previous.get('maximum', capacity))
            rivals = 1.6 + 0.65 * allied / max(0.1, capacity)
        attraction = bounded(
            (stock + capacity) / (average_stock + capacity), 0.75, 1.35
        )
        row = crowds.get(patch_key, [1.0, 0.0, tick])
        age = max(0, tick - row[2])
        factor = 1.0 + (row[0] - 1.0) / (1.0 + 0.04 * age)
        rivals = bounded(rivals * attraction * factor, 0.5, 10.0)
        first_probability = 1.0 / (1.0 + rivals)
        outcomes = []
        gross = 0.0
        for rank in range(5):
            probability = (
                first_probability if rank == 0
                else (1.0 - first_probability) / 4.0
            )
            ahead = 0.25 * rank * rivals * capacity
            harvest = min(maximum, max(0.0, stock - ahead))
            outcomes.append([probability, retention * harvest])
            gross += probability * harvest
        offers.append({
            'action': 'harvest',
            'target': target,
            'effort': effort,
            'cost': 0.08 * effort,
            'outcomes': outcomes,
            'gross': gross,
            'maximum': maximum,
            'stock': stock,
            'samples': row[1]
        })
    raids_allowed = broadcast.get(
        'raid_permission', broadcast.get('raids', True)
    )
    if raids_allowed:
        for offset in range(1, societies):
            target = (society + offset) % societies
            row = raids.get(str(target), [0.0, 0.0, 0.0, tick])
            discount = 1.0 / (1.0 + 0.045 * max(0, tick - row[3]))
            samples = discount * row[0]
            successes = discount * row[1]
            probability = (1.8 + successes) / (2.5 + samples)
            loot = bounded(
                (3.1 + discount * row[2]) / (2.0 + successes),
                0.0,
                1.656
            )
            offers.append({
                'action': 'raid',
                'target': target,
                'effort': 1.0,
                'cost': 0.08,
                'outcomes': [
                    [1.0 - probability, 0.0],
                    [probability, loot]
                ],
                'gross': probability * loot,
                'maximum': 1.656,
                'stock': 0.0,
                'samples': samples
            })
    values = [0.12 * index for index in range(11)]
    for planning_step in range(3):
        next_values = []
        for index in range(11):
            balance = 0.6 * index
            best = -1000000.0
            for offer in offers:
                value = consumption_return(balance, offer, transfer, values)
                best = max(best, value)
            next_values.append(best)
        values = next_values
    chosen = offers[0]
    best_score = consumption_return(wealth, chosen, transfer, values)
    for index, offer in enumerate(offers[1:]):
        score = consumption_return(wealth, offer, transfer, values)
        if wealth >= 2.55 and offer['action'] == 'raid':
            score += 0.012 / (1.0 + offer['samples'])
        score += 0.00002 * min(30.0, offer['stock'])
        score += 0.000001 * ((tick + 3 * member + index) % 7)
        if score > best_score:
            best_score = score
            chosen = offer
    patch_report = [
        [patch['id'], round(max(0.0, patch['stock']), 3)]
        for patch in patches
    ]
    return {
        'action': chosen['action'],
        'target': chosen['target'],
        'effort': chosen['effort'],
        'message': {
            'protocol': 'waterline_1',
            'planner': 'rank_scenarios',
            'patches': patch_report,
            'action': chosen['action'],
            'target': chosen['target'],
            'effort': round(chosen['effort'], 4),
            'capacity': round(capacity, 4),
            'yield': round(chosen['gross'], 4)
        },
        'state': {
            'crowds': crowds,
            'raids': raids,
            'passive': passive,
            'previous': {
                'action': chosen['action'],
                'target': chosen['target'],
                'wealth': wealth,
                'cost': min(wealth, chosen['cost']),
                'capacity': capacity,
                'maximum': chosen['maximum'],
                'stock': chosen['stock'],
                'gross': chosen['gross'],
                'tax': tax,
                'retention': retention,
                'transfer': transfer,
                'quoted': quoted
            }
        }
    }
def insurance_auction(wealths, flows, tax, budget):
    segments = []
    initial_loss = 0.0
    count = len(wealths)
    for index in range(count):
        flow = flows[index]
        claims = []
        for factor, probability in [[0.0, 0.25], [0.8, 0.5], [1.25, 0.25]]:
            harvest = min(flow['capacity'], factor * flow['harvest'])
            other = flow['other']
            if flow['action'] == 'raid':
                other = min(1.656, factor * flow['other'])
            immediate = (
                (1.0 - tax) * harvest + other - flow['cost']
            )
            future = max(0.0, immediate)
            for horizon, importance in [[1, 1.5], [2, 0.35], [4, 0.1]]:
                gap = max(
                    0.0,
                    0.85 * horizon - wealths[index]
                    - immediate - (horizon - 1) * future
                )
                if gap > 0.000001:
                    weight = probability * importance
                    claims.append([gap, weight])
                    initial_loss += gap * weight
        slope = sum(claim[1] for claim in claims)
        previous_gap = 0.0
        for gap, weight in sorted(claims):
            length = gap - previous_gap
            if length > 0.000001:
                segments.append([-slope, index, length])
            slope -= weight
            previous_gap = gap
    allocations = [0.0 for value in wealths]
    remaining = max(0.0, budget)
    benefit = 0.0
    for negative_slope, index, length in sorted(segments):
        if remaining <= 0.000001:
            break
        payment = min(remaining, length)
        allocations[index] += payment
        benefit -= negative_slope * payment
        remaining -= payment
    if remaining > 0.0:
        priorities = [
            1.0 / (0.5 + wealths[index] + allocations[index])
            for index in range(count)
        ]
        total = sum(priorities)
        for index in range(count):
            allocations[index] += remaining * priorities[index] / total
    return allocations, max(0.0, initial_loss - benefit)
def institution(observation, shared_state):
    state = shared_state or {}
    members = observation['members']
    count = len(members)
    treasury = max(0.0, observation['treasury'])
    infrastructure = max(0.0, observation['infrastructure'])
    if count == 0:
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
    reports = {}
    stocks = {}
    loads = {}
    for report in observation.get('reports', []):
        message = report.get('message', {}) or {}
        reports[str(report['member'])] = message
        for patch in message.get('patches', []) or []:
            key = str(patch[0])
            stocks[key] = max(stocks.get(key, 0.0), max(0.0, patch[1]))
        if 'patch' in message and 'stock' in message:
            key = str(message['patch'])
            stocks[key] = max(stocks.get(key, 0.0), max(0.0, message['stock']))
        action = message.get('action', 'harvest')
        target = message.get('target', message.get('patch'))
        if action == 'harvest' and target is not None:
            key = str(target)
            demand = (
                bounded(message.get('capacity', 2.4), 0.1, 2.76)
                * bounded(message.get('effort', 1.0), 0.0, 1.0)
            )
            loads[key] = loads.get(key, 0.0) + demand
    wealths = [max(0.0, member['wealth']) for member in members]
    liquid = treasury + sum(wealths)
    pressure = state.get('pressure', 0.0)
    if stocks:
        observed_pressure = sum(
            bounded(1.0 - stock / (2.4 * count), 0.0, 1.0)
            for stock in stocks.values()
        ) / len(stocks)
        pressure = 0.4 * pressure + 0.6 * observed_pressure
    income = state.get('income', 2.0 * count)
    if 'liquid' in state:
        construction = max(
            0.0,
            8.0 * count * (
                infrastructure - 0.96 * state.get('infrastructure', infrastructure)
            )
        )
        measured = bounded(
            liquid - state['liquid'] + 0.93 * count + construction,
            0.0,
            2.76 * count
        )
        rate = 0.5 if measured < income else 0.2
        income = (1.0 - rate) * income + rate * measured
    old_wealths = state.get('wealths', {})
    old_rebates = state.get('rebates', {})
    old_models = state.get('models', {})
    old_tax = bounded(state.get('tax', 0.25), 0.0, 0.8)
    models = {}
    flows = []
    contributions = 0.0
    for index, member in enumerate(members):
        key = str(member['id'])
        message = reports.get(key, {})
        action = message.get('action', 'harvest')
        capacity = bounded(message.get('capacity', 2.4), 0.1, 2.76)
        effort = bounded(message.get('effort', 1.0), 0.0, 1.0)
        harvest_mean, raid_mean = old_models.get(
            key, [bounded(income / count, 0.2, capacity), 0.95]
        )
        if key in old_wealths and wealths[index] > 0.00001:
            previous_cost = 0.0 if action == 'rest' else min(
                old_wealths[key], 0.08 * effort
            )
            receipt = (
                wealths[index] - old_wealths[key]
                + 0.85 + previous_cost - old_rebates.get(key, 0.0)
            )
            if action == 'harvest':
                measured = bounded(
                    receipt / max(0.2, 1.0 - old_tax), 0.0, capacity
                )
                harvest_mean = 0.75 * harvest_mean + 0.25 * measured
            elif action == 'raid':
                raid_mean = 0.75 * raid_mean + 0.25 * bounded(
                    receipt, 0.0, 1.656
                )
        models[key] = [harvest_mean, raid_mean]
        harvest = 0.0
        other = 0.0
        cost = 0.0 if action == 'rest' else min(wealths[index], 0.08 * effort)
        if action == 'harvest':
            target = str(message.get('target', message.get('patch')))
            estimate = harvest_mean
            if target in stocks:
                allied = max(
                    0.0, loads.get(target, 0.0) - capacity * effort
                )
                rivals = 2.6 + 0.65 * allied / max(0.1, capacity)
                estimate = min(capacity * effort, stocks[target] / rivals)
            if 'yield' in message:
                estimate = (
                    0.5 * estimate
                    + 0.5 * bounded(message['yield'], 0.0, capacity * effort)
                )
            harvest = min(
                capacity * effort, 0.4 * harvest_mean + 0.6 * estimate
            )
        elif action == 'raid':
            other = raid_mean
            if 'yield' in message:
                other = 0.6 * other + 0.4 * bounded(
                    message['yield'], 0.0, 1.656
                )
        elif action == 'contribute':
            amount = min(max(0.0, wealths[index] - cost), 2.0 * effort)
            contributions += amount
            other = -amount
        elif action == 'share':
            other = -min(max(0.0, wealths[index] - cost), 2.0 * effort)
        flows.append({
            'action': action,
            'capacity': capacity * effort,
            'harvest': max(0.0, harvest),
            'other': other,
            'cost': cost
        })
    total_harvest = sum(flow['harvest'] for flow in flows)
    surplus = max(0.0, liquid - 3.4 * count)
    construction_request = min(
        2.5 + 0.5 * pressure,
        0.08 * surplus * (0.2 + 0.8 * pressure)
    )
    best_loss = 1000000000.0
    selected = {}
    for tax in [0.0, 0.15, 0.30, 0.45, 0.60, 0.75]:
        pool = max(0.0, treasury + contributions + tax * total_harvest)
        safety_gap = 0.0
        for index, flow in enumerate(flows):
            guaranteed = max(
                0.0,
                wealths[index] - flow['cost'] + min(0.0, flow['other'])
            )
            safety_gap += max(0.0, 2.55 - guaranteed)
        investment = min(
            construction_request,
            0.45 * pool,
            max(0.0, pool - safety_gap)
        )
        budget = max(0.0, pool - investment)
        weights, risk = insurance_auction(wealths, flows, tax, budget)
        loss = (
            risk
            + 0.012 * tax * total_harvest
            + 0.005 * abs(tax - old_tax)
            - 0.055 * investment * (0.25 + 0.75 * pressure)
        )
        if loss < best_loss:
            best_loss = loss
            selected = {
                'tax': tax,
                'pool': pool,
                'investment': investment,
                'budget': budget,
                'weights': weights
            }
    weights = selected['weights']
    if sum(weights) <= 0.000001:
        weights = [1.0 / (0.3 + wealth) for wealth in wealths]
    weight_total = sum(weights)
    public_fraction = 0.0
    if selected['pool'] > 0.000001:
        public_fraction = selected['investment'] / selected['pool']
    rebates = {}
    passive_rebates = {}
    tax_returns = {}
    wealth_map = {}
    for index, member in enumerate(members):
        key = str(member['id'])
        share = weights[index] / weight_total
        marginal = (1.0 - public_fraction) * share
        rebate = selected['budget'] * share
        rebates[key] = round(rebate, 4)
        passive_rebates[key] = round(max(
            0.0,
            rebate - marginal * selected['tax'] * flows[index]['harvest']
        ), 4)
        tax_returns[key] = round(marginal, 5)
        wealth_map[key] = wealths[index]
    return {
        'tax_rate': selected['tax'],
        'public_fraction': public_fraction,
        'defense_fraction': 0.0,
        'reserve_fraction': 0.0,
        'redistribution': weights,
        'raid_permission': True,
        'messages': {
            'protocol': 'waterline_1',
            'planner': 'scenario_auction',
            'loads': loads,
            'rebates': rebates,
            'passive_rebates': passive_rebates,
            'tax_returns': tax_returns,
            'raids': True
        },
        'state': {
            'liquid': liquid,
            'infrastructure': infrastructure,
            'income': income,
            'pressure': pressure,
            'wealths': wealth_map,
            'rebates': rebates,
            'models': models,
            'tax': selected['tax']
        }
    }
# EVOLVE-BLOCK-END
