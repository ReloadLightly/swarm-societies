"""Initial members harvest locally; a modest fixed tax funds infrastructure."""
# EVOLVE-BLOCK-START
def bound(value, lower, upper):
    return max(lower, min(upper, value))
def liquidity_value(cash, remaining):
    cash = max(0.0, cash)
    food = min(0.85, cash)
    surplus = max(0.0, cash - food)
    insurance = min(surplus, 0.85 * min(2, max(0, remaining - 1)))
    return food + 0.22 * surplus + 0.62 * insurance
def crowd_prior(center):
    sizes = [1, 2, 3, 4, 6, 8]
    weights = []
    for size in sizes:
        distance = size - center
        weights.append(1.0 / (1.0 + distance * distance))
    total = sum(weights)
    return [weight / total for weight in weights]
def reported_cashflow(report, availability, tax, wealth):
    action = report.get('action', 'harvest')
    effort = bound(report.get('effort', 1.0), 0.0, 1.0)
    cost = 0.08 * effort
    if action == 'rest':
        return 0.0
    if action == 'harvest':
        capacity = 2.4 * report.get('productivity', 1.0) * effort
        return capacity * availability * (1.0 - tax) - cost
    if action == 'contribute' or action == 'share':
        return -cost - min(2.0 * effort, max(0.0, wealth - cost))
    if action == 'raid':
        return 0.90 * effort - cost
    return -cost
def member_policy(observation, private_state):
    tick = observation['tick']
    society = observation['society_id']
    member = observation['member_id']
    wealth = max(0.0, observation['wealth'])
    capacity = 2.4 * observation['productivity']
    tax = bound(observation['tax_rate'], 0.0, 0.8)
    remaining = max(1, 60 - tick)
    messages = observation.get('messages', {})
    sizes = [1, 2, 3, 4, 6, 8]
    crowds = private_state.get('crowds', {}).copy()
    raids = private_state.get('raids', {}).copy()
    credit = max(0.0, private_state.get('credit', 0.0))
    transfers = messages.get('previous_transfers', {})
    known_transfer = str(member) in transfers
    settled_credit = transfers.get(str(member), credit)
    if known_transfer:
        credit = max(0.0, settled_credit)
    previous_harvest = private_state.get('expected_harvest', 0.0)
    consecutive = private_state.get('tick', -2) == tick - 1
    if consecutive:
        old_action = private_state.get('action', 'rest')
        old_effort = private_state.get('effort', 0.0)
        old_wealth = private_state.get('wealth', wealth)
        receipt = wealth - old_wealth + 0.85 + 0.08 * old_effort
        if old_action == 'harvest':
            old_capacity = private_state.get('capacity', capacity)
            old_tax = private_state.get('tax', tax)
            maximum_net = old_capacity * (1.0 - old_tax)
            old_stock = private_state.get('stock', 0.0)
            if not known_transfer and receipt > maximum_net + 0.03:
                inferred_credit = bound(receipt - maximum_net, 0.0, 4.0)
                credit = 0.55 * credit + 0.45 * inferred_credit
                settled_credit = credit
            net_receipt = receipt - settled_credit
            reliable = wealth > 0.02 and net_receipt >= -0.05
            reliable = reliable and net_receipt <= maximum_net + 0.35
            if reliable and old_capacity > 0.01:
                realized = bound(net_receipt / max(0.2, 1.0 - old_tax), 0.0, old_capacity)
                previous_harvest = realized
                key = str(private_state.get('target', society))
                record = crowds.get(key, {})
                prior = crowd_prior(3.2)
                probabilities = record.get('probabilities', prior)
                tolerance = 0.12 if known_transfer else 0.35
                posterior = []
                for index, size in enumerate(sizes):
                    likelihood = 0.0
                    for position in range(size):
                        outcome = min(old_capacity, max(0.0, old_stock - 2.4 * position))
                        error = realized - outcome
                        likelihood += tolerance / (tolerance + error * error)
                    likelihood = 0.03 + likelihood / size
                    weight = 0.94 * probabilities[index] + 0.06 * prior[index]
                    posterior.append(weight * likelihood)
                total = max(0.000001, sum(posterior))
                crowds[key] = {
                    'probabilities': [value / total for value in posterior],
                    'visits': min(60, record.get('visits', 0) + 1)
                }
        elif old_action == 'raid':
            key = str(private_state.get('target', society))
            record = raids.get(key, [3.0, 1.0, 1.656, 0])
            reward = bound(receipt - settled_credit, 0.0, 1.656)
            success = 1.0 if reward > 0.20 and wealth > 0.02 else 0.0
            successes = 0.94 * record[0] + success
            failures = 0.94 * record[1] + 1.0 - success
            amount = record[2]
            if success > 0.0:
                amount = 0.60 * amount + 0.40 * reward
            raids[key] = [successes, failures, amount, min(60, record[3] + 1)]
    resource_memory = private_state.get('resources', {}).copy()
    for patch in observation['patches']:
        key = str(patch['id'])
        stock = max(0.0, patch['stock'])
        previous_resource = resource_memory.get(key, {})
        drift = previous_resource.get('drift', 3.0)
        if consecutive and previous_resource.get('tick', -2) == tick - 1:
            own_take = 0.0
            if private_state.get('action', '') == 'harvest':
                if private_state.get('target', society) == patch['id']:
                    own_take = previous_harvest
            observed_drift = bound(
                stock - previous_resource['stock'] + own_take,
                -12.0, 12.0
            )
            drift = 0.5 * drift + 0.5 * observed_drift
        resource_memory[key] = {
            'tick': tick,
            'stock': stock,
            'drift': drift
        }
    loads = {}
    for key, value in messages.get('harvest_loads', {}).items():
        loads[str(key)] = max(0.0, value)
    if not loads:
        for report in messages.get('reports', []):
            if report.get('member', -1) != member:
                message = report.get('message', {})
                if message.get('action', 'harvest') == 'harvest':
                    target = message.get('target', message.get('patch', society))
                    key = str(target)
                    loads[key] = loads.get(key, 0.0) + bound(message.get('effort', 1.0), 0.0, 1.0)
    elif private_state.get('action', '') == 'harvest':
        key = str(private_state.get('target', society))
        loads[key] = max(0.0, loads.get(key, 0.0) - private_state.get('effort', 1.0))
    visible = []
    chosen = society
    chosen_stock = 0.0
    chosen_effort = 0.0
    chosen_yield = 0.0
    harvest_score = -1000000.0
    for patch in observation['patches']:
        patch_id = patch['id']
        stock = max(0.0, patch['stock'])
        visible.append({'id': patch_id, 'stock': stock})
        key = str(patch_id)
        center = 3.2
        if loads:
            center = 2.0 + 0.60 * loads.get(key, 0.0)
            if patch_id != society:
                center += 0.5
        prior = crowd_prior(bound(center, 1.5, 6.0))
        record = crowds.get(key, {'probabilities': prior, 'visits': 0})
        probabilities = record['probabilities']
        crowds[key] = record
        effort = min(1.0, stock / max(0.01, capacity))
        reachable = capacity * effort
        score = 0.0
        expected_yield = 0.0
        for index, size in enumerate(sizes):
            probability = (0.95 * probabilities[index] + 0.05 * prior[index]) / size
            for position in range(size):
                harvest = min(reachable, max(0.0, stock - 2.4 * position))
                cash = wealth + credit + harvest * (1.0 - tax) - 0.08 * effort
                score += probability * liquidity_value(cash, remaining)
                expected_yield += probability * harvest
        opportunity_cost = 0.0
        drift = resource_memory[key]['drift']
        access = 1.0
        if patch_id != society:
            access = 1.0 / max(1, observation['n_societies'] - 1)
        for day in range(1, min(3, remaining)):
            future_stock = max(0.0, stock + day * drift)
            depleted_stock = max(0.0, future_stock - expected_yield)
            future_loss = 0.0
            for index, size in enumerate(sizes):
                probability = (
                    0.95 * probabilities[index] + 0.05 * prior[index]
                ) / size
                for position in range(size):
                    preserved_yield = min(
                        capacity, max(0.0, future_stock - 2.4 * position)
                    )
                    depleted_yield = min(
                        capacity, max(0.0, depleted_stock - 2.4 * position)
                    )
                    future_loss += probability * (
                        preserved_yield - depleted_yield
                    )
            opportunity_cost += 0.55 * future_loss / day
        score -= 0.22 * (1.0 - tax) * access * opportunity_cost
        score += 0.000002 * min(100.0, stock)
        score += 0.0015 / (1.0 + record.get('visits', 0))
        if score > harvest_score:
            harvest_score = score
            chosen = patch_id
            chosen_stock = stock
            chosen_effort = effort
            chosen_yield = expected_yield
    action = 'rest'
    target = society
    effort = 0.0
    best_score = liquidity_value(wealth + credit, remaining)
    if chosen_effort > 0.0 and harvest_score > best_score + 0.00001:
        action = 'harvest'
        target = chosen
        effort = chosen_effort
        best_score = harvest_score
    if messages.get('raid_permission', True):
        societies = observation['n_societies']
        for offset in range(societies):
            other = (tick + member + offset) % societies
            if other != society:
                record = raids.get(str(other), [3.0, 1.0, 1.656, 0])
                probability = record[0] / max(0.01, record[0] + record[1])
                success_value = liquidity_value(wealth + credit + record[2] - 0.08, remaining)
                failure_value = liquidity_value(wealth + credit - 0.08, remaining)
                score = probability * success_value + (1.0 - probability) * failure_value
                score += 0.006 / (1.0 + record[3])
                if score > best_score + 0.015:
                    action = 'raid'
                    target = other
                    effort = 1.0
                    best_score = score
    return {
        'action': action,
        'target': target,
        'effort': effort,
        'message': {
            'patch': chosen,
            'stock': chosen_stock,
            'patches': visible,
            'action': action,
            'target': target,
            'effort': effort,
            'productivity': observation['productivity'],
            'wealth': wealth,
            'expected_harvest': chosen_yield
        },
        'state': {
            'tick': tick,
            'wealth': wealth,
            'action': action,
            'target': target,
            'effort': effort,
            'capacity': capacity * effort,
            'stock': chosen_stock,
            'tax': tax,
            'credit': credit,
            'expected_harvest': chosen_yield,
            'resources': resource_memory,
            'crowds': crowds,
            'raids': raids
        }
    }
def institution(observation, shared_state):
    members = observation['members']
    count = max(1, len(members))
    tick = observation['tick']
    remaining = max(1, 60 - tick)
    society = observation['society_id']
    treasury = max(0.0, observation['treasury'])
    infrastructure = max(0.0, observation['infrastructure'])
    tax = 0.8
    reports = {}
    loads = {}
    stock_signals = []
    for report in observation.get('reports', []):
        message = report.get('message', {})
        reports[str(report['member'])] = message
        stocks = [max(0.0, patch['stock']) for patch in message.get('patches', [])]
        if 'stock' in message:
            stocks.append(max(0.0, message['stock']))
        if stocks:
            stock_signals.append(max(stocks))
        if message.get('action', 'harvest') == 'harvest':
            key = str(message.get('target', message.get('patch', society)))
            loads[key] = loads.get(key, 0.0) + bound(message.get('effort', 1.0), 0.0, 1.0)
    old_people = shared_state.get('people', {})
    old_tax = shared_state.get('tax', tax)
    old_public = shared_state.get('public', 0.0)
    old_defense = shared_state.get('defense', 0.0)
    old_treasury = shared_state.get('treasury', 0.0)
    observed_pool = shared_state.get('pool', 2.2 * count * tax)
    measured = False
    if old_people and old_public > 0.000001:
        investment = 8.0 * count * (infrastructure - 0.96 * shared_state.get('infrastructure', infrastructure))
        if investment >= -0.000001:
            observed_pool = bound(max(0.0, investment) / old_public, 0.0, old_treasury + 8.0 * count)
            measured = True
    previous_distribution = observed_pool * max(0.0, 1.0 - old_public - old_defense)
    observed_flow = max(0.0, observed_pool - old_treasury)
    harvest_capacity = 0.0
    previous_contributions = 0.0
    current_contributions = 0.0
    for member in members:
        key = str(member['id'])
        report = reports.get(key, {})
        action = report.get('action', 'harvest')
        effort = bound(report.get('effort', 1.0), 0.0, 1.0)
        if action == 'harvest':
            harvest_capacity += 2.4 * report.get('productivity', 1.0) * effort
        elif action == 'contribute':
            old_wealth = old_people.get(key, {}).get('wealth', member['wealth'])
            previous_contributions += min(2.0 * effort, max(0.0, old_wealth - 0.08 * effort))
            current_contributions += min(2.0 * effort, max(0.0, member['wealth'] - 0.08 * effort))
    stock_signal = 1.0
    if stock_signals:
        stock_signal = bound(sum(stock_signals) / len(stock_signals) / (2.4 * count), 0.08, 1.0)
    history = list(shared_state.get('yield_history', []))
    realized = shared_state.get('availability', stock_signal)
    if measured and harvest_capacity > 0.01 and old_tax > 0.01:
        realized = bound((observed_flow - previous_contributions) / (old_tax * harvest_capacity), 0.0, 1.0)
        history.append(realized)
    elif not history:
        history.append(stock_signal)
    while len(history) > 5:
        history.pop(0)
    ordered = sorted(history)
    middle = ordered[len(ordered) // 2]
    latest = history[-1]
    availability = bound(0.60 * latest + 0.40 * middle, 0.04, 1.0)
    if latest < 0.72 * middle:
        availability = max(0.04, latest)
    if not measured:
        availability = bound(0.65 * availability + 0.35 * stock_signal, 0.04, 1.0)
    low_availability = max(0.02, min(min(history), 0.78 * availability))
    high_availability = min(1.0, max(availability, middle) + 0.08)
    previous_transfers = {}
    people = {}
    signed_loss = 0.0
    loss_observations = 0
    old_defense_cash = observed_pool * old_defense
    old_suppression = (1.0 + old_defense_cash) * (1.0 + 0.4 * old_defense_cash)
    old_expected_loss = shared_state.get('threat', 0.0) / old_suppression
    for member in members:
        key = str(member['id'])
        wealth = max(0.0, member['wealth'])
        previous = old_people.get(key, {})
        report = reports.get(key, {})
        transfer = previous_distribution * previous.get('share', 0.0)
        previous_transfers[key] = transfer
        bias = previous.get('bias', 0.0)
        if previous and measured:
            model = reported_cashflow(report, realized, old_tax, previous['wealth'])
            observed_income = wealth - previous['wealth'] - transfer + 0.85
            residual = observed_income - model
            if report.get('action', 'harvest') != 'raid':
                signed_loss -= residual
                loss_observations += 1
                adjusted = residual + old_expected_loss / count
                bias = bound(0.65 * bias + 0.35 * adjusted, -0.45, 0.45)
        people[key] = {'wealth': wealth, 'bias': bias, 'share': 0.0}
    threat_history = list(shared_state.get('threat_history', []))
    if measured and loss_observations > 0:
        loss = max(0.0, signed_loss * count / loss_observations)
        threat_history.append(bound(loss * old_suppression, 0.0, 12.0))
    if not threat_history:
        threat_history.append(0.0)
    while len(threat_history) > 5:
        threat_history.pop(0)
    threat = 0.60 * sum(threat_history) / len(threat_history) + 0.40 * threat_history[-1]
    expected_flow = harvest_capacity * availability * tax + current_contributions
    pool = max(0.05, treasury + expected_flow)
    life = 0.0
    survival = 1.0
    for step in range(remaining):
        life += survival
        survival *= 0.96
    scarcity = bound(1.0 - availability + 0.22, 0.08, 0.85)
    capital_bid = bound(0.0025 * life + 0.42 * life * scarcity / (8.0 * count), 0.003, 0.32)
    horizon = min(5, remaining)
    deadline_weights = [2.5, 0.55, 0.30, 0.17, 0.09]
    scenarios = [
        [availability, 0.60, 1.0],
        [low_availability, 0.30, 1.6],
        [high_availability, 0.10, 0.35]
    ]
    claims = []
    for member in members:
        key = str(member['id'])
        wealth = max(0.0, member['wealth'])
        report = reports.get(key, {})
        action = report.get('action', 'harvest')
        effort = bound(report.get('effort', 1.0), 0.0, 1.0)
        productivity = report.get('productivity', 1.0)
        bias = people[key]['bias']
        member_claims = []
        for scenario_index, scenario in enumerate(scenarios):
            fraction = scenario[0]
            probability = scenario[1]
            loss_multiplier = scenario[2]
            current_income = reported_cashflow(report, fraction, tax, wealth)
            if action == 'raid':
                raid_income = [0.90, 0.10, 1.40][scenario_index]
                current_income = raid_income * effort - 0.08 * effort
            future_income = current_income
            if action == 'contribute' or action == 'share':
                future_income = 2.4 * productivity * fraction * (1.0 - tax) - 0.08
            accumulated_income = 0.0
            for day in range(horizon):
                income = current_income if day == 0 else future_income
                accumulated_income += income + bias / (1.0 + 0.5 * day)
                exposure = (day + 1) * threat * loss_multiplier / count
                need = 0.85 * (day + 1) - wealth - accumulated_income + exposure
                member_claims.append([need, probability * deadline_weights[day], exposure])
        claims.append(member_claims)
    gifts = [0.0 for member in members]
    defense_cash = 0.0
    defense_limit = min(1.6, 0.25 * pool)
    quantum = 0.99 * pool / 24.0
    for auction_round in range(24):
        protection = 1.0 - 1.0 / ((1.0 + defense_cash) * (1.0 + 0.4 * defense_cash))
        defense_quantum = min(quantum, max(0.0, defense_limit - defense_cash))
        next_defense = defense_cash + defense_quantum
        next_protection = 1.0 - 1.0 / ((1.0 + next_defense) * (1.0 + 0.4 * next_defense))
        protection_gain = next_protection - protection
        defense_bid = 0.0
        best_bid = capital_bid
        winner = -1
        for index in range(len(members)):
            bid = 0.0
            for claim in claims[index]:
                gap = max(0.0, claim[0] - gifts[index] - claim[2] * protection)
                bid += claim[1] * min(quantum, gap) / quantum
                defense_bid += claim[1] * min(claim[2] * protection_gain, gap) / max(0.000001, defense_quantum)
            if bid > best_bid + 0.000001:
                best_bid = bid
                winner = index
        if defense_quantum > 0.000001 and defense_bid > best_bid + 0.000001:
            defense_cash += defense_quantum
        elif winner >= 0:
            gifts[winner] += quantum
        else:
            break
    distribution_cash = sum(gifts)
    weights = gifts
    if distribution_cash <= 0.000001:
        weights = [1.0 for member in members]
    weight_sum = max(0.000001, sum(weights))
    for index, member in enumerate(members):
        people[str(member['id'])]['share'] = weights[index] / weight_sum
    defense = defense_cash / pool
    public = max(0.01, 1.0 - defense - distribution_cash / pool)
    return {
        'tax_rate': tax,
        'public_fraction': public,
        'defense_fraction': defense,
        'reserve_fraction': 0.0,
        'redistribution': weights,
        'raid_permission': False,
        'messages': {
            'raid_permission': False,
            'previous_transfers': previous_transfers,
            'harvest_loads': loads,
            'scarcity': availability < 0.70,
            'insurance_horizon': horizon
        },
        'state': {
            'people': people,
            'tax': tax,
            'public': public,
            'defense': defense,
            'pool': pool,
            'treasury': treasury,
            'infrastructure': infrastructure,
            'availability': availability,
            'yield_history': history,
            'threat': threat,
            'threat_history': threat_history
        }
    }
# EVOLVE-BLOCK-END