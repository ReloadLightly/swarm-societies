"""Initial members harvest locally; a modest fixed tax funds infrastructure."""
# EVOLVE-BLOCK-START
def bounded(value, lower, upper):
    return max(lower, min(upper, value))
def harvest_outcomes(stock, capacity, shift):
    depletion = [0.0, 1.2, 2.4, 4.8, 7.2, 9.6, 14.4]
    return [
        min(capacity, max(0.0, stock - max(0.0, value + shift)))
        for value in depletion
    ]
def member_cash_score(wealth, income, transfer, remaining):
    cash = max(0.0, wealth + income + transfer)
    consumption = min(0.85, cash)
    savings = max(0.0, cash - consumption)
    useful_buffer = min(2.55, 0.45 * max(0, remaining - 1))
    return consumption + 0.2 * savings + 0.18 * min(
        savings, useful_buffer
    )
def member_policy(observation, private_state):
    private_state = private_state or {}
    tick = observation['tick']
    society = observation['society_id']
    member = observation['member_id']
    wealth = max(0.0, observation['wealth'])
    capacity = 2.4 * observation['productivity']
    tax = bounded(observation['tax_rate'], 0.0, 0.8)
    remaining = max(1, 60 - tick)
    messages = observation.get('messages', {})
    prior = [0.18, 0.16, 0.20, 0.20, 0.13, 0.08, 0.05]
    models = private_state.get('models', {}).copy()
    raids = private_state.get('raids', {}).copy()
    aid = private_state.get('aid', 0.0)
    transfers = messages.get('previous_transfers', {})
    member_key = str(member)
    known_transfer = member_key in transfers
    previous_transfer = transfers.get(member_key, aid)
    previous_action = private_state.get('action', '')
    previous_wealth = private_state.get('wealth', wealth)
    previous_effort = private_state.get('effort', 0.0)
    previous_cost = min(previous_wealth, 0.08 * previous_effort)
    recovered_income = (
        wealth - previous_wealth + 0.85 + previous_cost
        - previous_transfer
    )
    if known_transfer:
        aid = 0.5 * aid + 0.5 * max(0.0, previous_transfer)
    elif previous_action == 'harvest':
        old_capacity = private_state.get('capacity', capacity)
        old_tax = private_state.get('tax', tax)
        if private_state.get('stock', 0.0) >= 22.0 and wealth > 0.02:
            full_income = old_capacity * previous_effort * (1.0 - old_tax)
            excess = (
                wealth - previous_wealth + 0.85 + previous_cost
                - full_income
            )
            if excess >= 0.0:
                aid = 0.7 * aid + 0.3 * min(3.0, excess)
    if previous_action == 'harvest' and wealth > 0.02:
        key = str(private_state.get('target', society))
        record = models.get(key, {})
        weights = record.get('weights', prior)
        old_capacity = private_state.get('capacity', capacity)
        old_tax = private_state.get('tax', tax)
        outcomes = harvest_outcomes(
            private_state.get('stock', 0.0),
            old_capacity * previous_effort,
            private_state.get('shift', 0.0)
        )
        limit = old_capacity * previous_effort * (1.0 - old_tax)
        if recovered_income >= -0.05 and recovered_income <= limit + 0.3:
            noise = 0.08 + 0.25 * (1.0 - old_tax)
            if not known_transfer:
                noise += 0.22
            posterior = []
            for index, amount in enumerate(outcomes):
                error = abs(
                    recovered_income - amount * (1.0 - old_tax)
                )
                scale = noise + error
                likelihood = noise * noise / (scale * scale)
                posterior.append(weights[index] * likelihood)
            normalizer = max(0.000001, sum(posterior))
            updated = [
                0.88 * posterior[index] / normalizer + 0.12 * prior[index]
                for index in range(len(prior))
            ]
            models[key] = {
                'weights': updated,
                'samples': min(60, record.get('samples', 0) + 1)
            }
    if previous_action == 'raid' and wealth > 0.02:
        key = str(private_state.get('target', society))
        record = raids.get(key, {})
        success = 0.94 * record.get('success', 2.25)
        failure = 0.94 * record.get('failure', 0.75)
        payout = record.get('payout', 1.45)
        if recovered_income > 0.2:
            success += 1.0
            payout = 0.7 * payout + 0.3 * bounded(
                recovered_income, 0.2, 1.656
            )
        else:
            failure += 1.0
        raids[key] = {
            'success': success,
            'failure': failure,
            'payout': payout,
            'samples': min(60, record.get('samples', 0) + 1)
        }
    loads = {}
    informed = False
    if 'harvest_loads' in messages:
        informed = True
        for key, value in messages['harvest_loads'].items():
            loads[str(key)] = max(0.0, value)
        if previous_action == 'harvest':
            key = str(private_state.get('target', society))
            loads[key] = max(
                0.0, loads.get(key, 0.0) - previous_effort
            )
    else:
        for report in messages.get('reports', []):
            if report.get('member', -1) != member:
                report_message = report.get('message', {})
                if report_message.get('action', '') == 'harvest':
                    informed = True
                    key = str(report_message.get(
                        'target', report_message.get('patch', society)
                    ))
                    loads[key] = loads.get(key, 0.0) + bounded(
                        report_message.get('effort', 1.0), 0.0, 1.0
                    )
    planned = messages.get('planned_transfers', {}).get(member_key, aid)
    fiscal_return = bounded(
        messages.get('fiscal_return', {}).get(member_key, 0.0),
        0.0, 1.0
    )
    expected_previous_harvest = messages.get(
        'expected_harvest', {}
    ).get(member_key, 0.0)
    base_transfer = max(
        0.0, planned - fiscal_return * tax * expected_previous_harvest
    )
    retained_fraction = 1.0 - tax + fiscal_return * tax
    best_score = member_cash_score(
        wealth, 0.0, base_transfer, remaining
    )
    action = 'rest'
    target = society
    effort = 0.0
    selected_stock = 0.0
    selected_shift = 0.0
    report_patch = society
    report_stock = 0.0
    best_harvest_score = -1000000.0
    visible = []
    for patch in observation['patches']:
        patch_id = patch['id']
        stock = max(0.0, patch['stock'])
        visible.append({'id': patch_id, 'stock': stock})
        key = str(patch_id)
        record = models.get(key, {})
        weights = record.get('weights', prior)
        shift = 0.0
        if informed:
            shift = bounded(
                0.75 * (loads.get(key, 0.0) - 1.5), -1.125, 3.0
            )
        maximum_effort = min(1.0, stock / max(0.01, capacity))
        if maximum_effort <= 0.0:
            continue
        efforts = [maximum_effort]
        if stock < 8.0:
            efforts.append(0.5 * maximum_effort)
        for trial_effort in efforts:
            outcomes = harvest_outcomes(
                stock, capacity * trial_effort, shift
            )
            cost = min(wealth, 0.08 * trial_effort)
            score = 0.0
            for index, amount in enumerate(outcomes):
                score += weights[index] * member_cash_score(
                    wealth,
                    retained_fraction * amount - cost,
                    base_transfer,
                    remaining
                )
            score += 0.0015 / (1.0 + record.get('samples', 0))
            score += 0.00001 * min(100.0, stock)
            if score > best_harvest_score:
                best_harvest_score = score
                report_patch = patch_id
                report_stock = stock
            if score > best_score:
                best_score = score
                action = 'harvest'
                target = patch_id
                effort = trial_effort
                selected_stock = stock
                selected_shift = shift
    if messages.get('raid_permission', True):
        societies = max(1, observation['n_societies'])
        for offset in range(societies):
            other = (tick + 3 * member + society + offset) % societies
            if other == society:
                continue
            record = raids.get(str(other), {})
            success = record.get('success', 2.25)
            failure = record.get('failure', 0.75)
            probability = success / max(0.01, success + failure)
            payout = record.get('payout', 1.45)
            cost = min(wealth, 0.08)
            score = probability * member_cash_score(
                wealth, payout - cost, base_transfer, remaining
            )
            score += (1.0 - probability) * member_cash_score(
                wealth, -cost, base_transfer, remaining
            )
            score += (
                0.018 * min(1.0, remaining / 12.0)
                / (1.0 + record.get('samples', 0))
            )
            if score > best_score:
                best_score = score
                action = 'raid'
                target = other
                effort = 1.0
                selected_stock = 0.0
                selected_shift = 0.0
    return {
        'action': action,
        'target': target,
        'effort': effort,
        'message': {
            'patch': report_patch,
            'stock': report_stock,
            'patches': visible,
            'action': action,
            'target': target,
            'effort': effort,
            'productivity': observation['productivity'],
            'wealth': wealth
        },
        'state': {
            'wealth': wealth,
            'capacity': capacity,
            'tax': tax,
            'action': action,
            'target': target,
            'effort': effort,
            'stock': selected_stock,
            'shift': selected_shift,
            'aid': aid,
            'models': models,
            'raids': raids
        }
    }
def forecast_flows(units, wealths, availability, tax, stage):
    before = []
    revenue = 0.0
    for index, unit in enumerate(units):
        wealth = wealths[index]
        mode = unit['mode']
        effort = unit['effort']
        if stage > 0 and mode in ['contribute', 'share'] and wealth < 2.5:
            mode = 'harvest'
            effort = 1.0
        cost = min(wealth, 0.08 * effort) if mode != 'rest' else 0.0
        income = 0.0
        if mode == 'harvest':
            harvest = unit['capacity'] * effort * availability
            income = harvest * (1.0 - tax)
            revenue += harvest * tax
        elif mode in ['contribute', 'share']:
            payment = min(2.0 * effort, max(0.0, wealth - cost))
            income = -payment
            if mode == 'contribute':
                revenue += payment
        elif mode == 'raid':
            income = unit['raid_gain'] * effort
        before.append(wealth + income - cost - 0.85)
    return before, revenue
def survival_allocation(before, pool, safety, defense):
    available = max(0.0, pool * (0.995 - defense))
    urgent = [max(0.0, -value) for value in before]
    cushions = [max(0.0, safety - max(0.0, value)) for value in before]
    urgent_total = sum(urgent)
    cushion_total = sum(cushions)
    if urgent_total >= available and urgent_total > 0.0:
        payments = [
            available * amount / urgent_total for amount in urgent
        ]
    else:
        extra = min(cushion_total, max(0.0, available - urgent_total))
        payments = [
            urgent[index] + extra * cushions[index] / max(0.000001, cushion_total)
            for index in range(len(before))
        ]
    total = sum(payments)
    if total > 0.000001:
        shares = [payment / total for payment in payments]
    else:
        shares = [1.0 / max(1, len(before)) for value in before]
    public = bounded(
        1.0 - defense - total / max(0.000001, pool),
        0.005, 1.0 - defense
    )
    return public, shares
def policy_projection(
    units, initial_wealth, infrastructure, treasury, availability,
    threat, policy, horizon, tail, liquidity_credit
):
    wealths = initial_wealth.copy()
    capital = infrastructure
    cash = treasury
    capital_total = 0.0
    shortage_total = 0.0
    count = max(1, len(units))
    for stage in range(horizon):
        supply = bounded(
            availability + 0.45 * (capital - infrastructure) / count,
            0.0, 1.0
        )
        before, flow = forecast_flows(
            units, wealths, supply, policy['tax'], stage
        )
        pool = max(0.0, cash + flow)
        defense = policy['defense']
        defense_cash = defense * pool
        loss = threat / (
            (1.0 + defense_cash) * (1.0 + 0.4 * defense_cash)
        )
        before = [value - loss / count for value in before]
        if stage == 0:
            public = policy['public']
            shares = policy['shares']
        else:
            public, shares = survival_allocation(
                before, pool, policy['safety'], defense
            )
        redistribution = max(0.0, pool * (1.0 - public - defense))
        next_wealth = []
        for index, value in enumerate(before):
            balance = value + redistribution * shares[index]
            shortage_total += min(0.85, max(0.0, -balance))
            next_wealth.append(max(0.0, balance))
        wealths = next_wealth
        capital = 0.96 * capital + public * pool / (8.0 * count)
        capital_total += capital
        cash = 0.0
    return (
        capital_total + tail * capital - 25.0 * shortage_total
        + liquidity_credit * sum(min(1.0, value) for value in wealths)
    )
def institution(observation, shared_state):
    shared_state = shared_state or {}
    members = observation['members']
    count = max(1, len(members))
    tick = observation['tick']
    treasury = max(0.0, observation['treasury'])
    infrastructure = max(0.0, observation['infrastructure'])
    remaining = max(1, 60 - tick)
    previous_people = shared_state.get('people', {})
    previous_tax = shared_state.get('tax', 0.8)
    previous_public = shared_state.get('public', 0.0)
    previous_defense = shared_state.get('defense', 0.0)
    previous_treasury = shared_state.get('treasury', 0.0)
    reports = {}
    harvest_loads = {}
    stock_hints = []
    for report in observation.get('reports', []):
        message = report.get('message', {})
        reports[str(report['member'])] = message
        observed_stocks = [
            max(0.0, patch['stock'])
            for patch in message.get('patches', [])
        ]
        if 'stock' in message:
            observed_stocks.append(max(0.0, message['stock']))
        if observed_stocks:
            stock_hints.append(max(observed_stocks))
        if message.get('action', '') == 'harvest':
            patch = message.get('target', message.get('patch', -1))
            if patch != -1:
                key = str(patch)
                harvest_loads[key] = harvest_loads.get(key, 0.0) + bounded(
                    message.get('effort', 1.0), 0.0, 1.0
                )
    measured = False
    measured_pool = shared_state.get('pool', 0.0)
    if previous_people and previous_public > 0.000001:
        investment = 8.0 * count * (
            infrastructure - 0.96 * shared_state.get(
                'infrastructure', infrastructure
            )
        )
        if investment >= -0.000001:
            measured_pool = bounded(
                max(0.0, investment) / previous_public,
                0.0, previous_treasury + 6.0 * count
            )
            measured = True
    old_distribution = measured_pool * max(
        0.0, 1.0 - previous_public - previous_defense
    )
    units = []
    wealths = []
    old_wealths = []
    previous_transfers = {}
    harvest_capacity = 0.0
    contributions = 0.0
    raid_count = 0
    old_threat = shared_state.get('threat', 0.0)
    for member in members:
        key = str(member['id'])
        previous = previous_people.get(key, {})
        message = reports.get(key, {})
        wealth = max(0.0, member['wealth'])
        old_wealth = previous.get('wealth', wealth)
        productivity = bounded(
            message.get('productivity', previous.get('productivity', 1.0)),
            0.5, 1.5
        )
        mode = message.get('action', previous.get('mode', 'harvest'))
        effort = bounded(
            message.get('effort', previous.get('effort', 1.0)), 0.0, 1.0
        )
        transfer = old_distribution * previous.get('share', 0.0)
        previous_transfers[key] = transfer
        raid_gain = previous.get('raid_gain', 0.9)
        if mode == 'raid':
            raid_count += 1
            if previous and measured and wealth > 0.02:
                recovered = (
                    wealth - old_wealth - transfer + 0.85
                    + min(old_wealth, 0.08 * effort) + old_threat / count
                )
                raid_gain = 0.65 * raid_gain + 0.35 * bounded(
                    recovered / max(0.1, effort), 0.0, 1.656
                )
        elif mode == 'harvest':
            harvest_capacity += 2.4 * productivity * effort
        elif mode == 'contribute':
            contributions += min(
                2.0 * effort, max(0.0, old_wealth - 0.08 * effort)
            )
        units.append({
            'id': member['id'],
            'capacity': 2.4 * productivity,
            'mode': mode,
            'effort': effort,
            'raid_gain': raid_gain
        })
        wealths.append(wealth)
        old_wealths.append(old_wealth)
    stock_hint = 1.0
    if stock_hints:
        stock_hint = bounded(
            sum(stock_hints) / len(stock_hints)
            / max(1.0, 1.8 * count),
            0.03, 1.0
        )
    old_yield = shared_state.get('yield', 0.95)
    sample = old_yield
    observed_yield = False
    if measured and previous_tax > 0.01 and harvest_capacity > 0.1:
        sample = bounded(
            (measured_pool - previous_treasury - contributions)
            / (previous_tax * harvest_capacity),
            0.0, 1.0
        )
        observed_yield = True
    elif stock_hints:
        sample = stock_hint
    history = shared_state.get('yield_history', []).copy()
    history.append(sample)
    if len(history) > 6:
        history.pop(0)
    ordered = sorted(history)
    median = ordered[len(ordered) // 2]
    availability = 0.55 * sample + 0.45 * median
    shock = sample < old_yield - 0.18
    if shock:
        availability = min(availability, sample + 0.05)
        history = [sample]
    volatility = (
        0.7 * shared_state.get('volatility', 0.05)
        + 0.3 * abs(sample - old_yield)
    )
    if stock_hints:
        availability = 0.85 * availability + 0.15 * stock_hint
    availability = bounded(availability, 0.0, 1.0)
    threat = old_threat
    if measured and previous_people and observed_yield:
        expected_before, unused_flow = forecast_flows(
            units, old_wealths, sample, previous_tax, 0
        )
        unexplained_loss = max(
            0.0,
            sum(expected_before) + old_distribution - sum(wealths)
            - 0.15 - 0.6 * raid_count
        )
        old_defense_cash = measured_pool * previous_defense
        untreated_loss = unexplained_loss * (
            (1.0 + old_defense_cash) * (1.0 + 0.4 * old_defense_cash)
        )
        threat = 0.65 * threat + 0.35 * min(12.0, untreated_loss)
    uncertainty = bounded(
        0.10 + 0.8 * volatility + (0.12 if shock else 0.0),
        0.10, 0.45
    )
    adverse_yield = max(
        0.0, availability * (1.0 - uncertainty) - 0.025
    )
    horizon = min(3, remaining)
    decay = 1.0
    tail = 0.0
    for step in range(min(20, max(0, remaining - horizon))):
        decay *= 0.96
        tail += decay
    tail = min(8.0, 0.6 * tail)
    liquidity_credit = 0.12 * min(
        1.0, max(0, remaining - horizon) / 8.0
    )
    terminal_limit = 0.06 + 0.45 * max(0, remaining - 1)
    lean = min(
        terminal_limit, 0.35 + 1.3 * volatility + 0.20 * threat / count
    )
    insured = min(
        terminal_limit, 1.0 + 2.0 * volatility + 0.40 * threat / count
    )
    lower_tax = bounded(
        1.0 - 0.93 / max(0.9, 2.4 * availability), 0.32, 0.68
    )
    best_score = -1000000000.0
    selected = {}
    selected_pool = 0.0
    for tax in [0.8, lower_tax]:
        nominal_before, nominal_flow = forecast_flows(
            units, wealths, availability, tax, 0
        )
        pool = max(0.0, treasury + nominal_flow)
        defense_cash = min(
            1.6,
            0.22 * pool,
            max(0.0, 0.72 * (threat - 0.7) / (1.0 + 0.25 * threat))
        )
        defense_options = [0.0]
        if defense_cash > 0.02:
            defense_options.append(defense_cash / max(0.000001, pool))
        for defense in defense_options:
            protection = defense * pool
            expected_loss = threat / (
                (1.0 + protection) * (1.0 + 0.4 * protection)
            )
            before = [
                value - expected_loss / count for value in nominal_before
            ]
            for safety in [lean, insured]:
                public, shares = survival_allocation(
                    before, pool, safety, defense
                )
                policy = {
                    'tax': tax,
                    'defense': defense,
                    'public': public,
                    'shares': shares,
                    'safety': safety
                }
                normal_score = policy_projection(
                    units, wealths, infrastructure, treasury,
                    availability, threat, policy, horizon, tail,
                    liquidity_credit
                )
                adverse_score = policy_projection(
                    units, wealths, infrastructure, treasury,
                    adverse_yield, threat, policy, horizon, tail,
                    liquidity_credit
                )
                score = 0.65 * normal_score + 0.35 * adverse_score
                if score > best_score:
                    best_score = score
                    selected = policy
                    selected_pool = pool
    tax = selected['tax']
    public = selected['public']
    defense = selected['defense']
    shares = selected['shares']
    distribution_fraction = max(0.0, 1.0 - public - defense)
    planned_transfers = {}
    fiscal_return = {}
    expected_harvest = {}
    people = {}
    for index, unit in enumerate(units):
        key = str(unit['id'])
        share = shares[index]
        planned_transfers[key] = (
            selected_pool * distribution_fraction * share
        )
        fiscal_return[key] = distribution_fraction * share
        expected_harvest[key] = (
            unit['capacity'] * unit['effort'] * availability
            if unit['mode'] == 'harvest' else 0.0
        )
        people[key] = {
            'wealth': wealths[index],
            'share': share,
            'productivity': unit['capacity'] / 2.4,
            'mode': unit['mode'],
            'effort': unit['effort'],
            'raid_gain': unit['raid_gain']
        }
    return {
        'tax_rate': tax,
        'public_fraction': public,
        'defense_fraction': defense,
        'reserve_fraction': 0.0,
        'redistribution': shares,
        'raid_permission': False,
        'messages': {
            'raid_permission': False,
            'previous_transfers': previous_transfers,
            'planned_transfers': planned_transfers,
            'fiscal_return': fiscal_return,
            'expected_harvest': expected_harvest,
            'harvest_loads': harvest_loads,
            'buffer': selected['safety'],
            'scarcity': availability < 0.7
        },
        'state': {
            'people': people,
            'tax': tax,
            'public': public,
            'defense': defense,
            'treasury': treasury,
            'pool': selected_pool,
            'infrastructure': infrastructure,
            'yield': availability,
            'yield_history': history,
            'volatility': volatility,
            'threat': threat
        }
    }
# EVOLVE-BLOCK-END
