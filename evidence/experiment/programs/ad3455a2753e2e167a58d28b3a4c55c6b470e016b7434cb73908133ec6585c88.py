"""Initial members harvest locally; a modest fixed tax funds infrastructure."""
# EVOLVE-BLOCK-START
def member_policy(observation, private_state):
    tick = observation['tick']
    society = observation['society_id']
    member = observation['member_id']
    wealth = observation['wealth']
    messages = observation.get('messages', {})
    capacity = 2.4 * observation['productivity']
    tax = observation['tax_rate']
    raid_values = private_state.get('raid_values', {}).copy()
    raid_counts = private_state.get('raid_counts', {}).copy()
    if private_state.get('action', '') == 'raid':
        key = str(private_state.get('target', society))
        transfers = messages.get('previous_transfers', {})
        reward = (
            wealth - private_state.get('wealth', wealth)
            + 0.85 + 0.08 * private_state.get('effort', 1.0)
            - transfers.get(str(member), 0.0)
        )
        reward = max(0.0, min(1.656, reward))
        if wealth <= 0.01:
            reward = 0.0
        raid_values[key] = (
            0.65 * raid_values.get(key, 0.82) + 0.35 * reward
        )
        raid_counts[key] = min(60, raid_counts.get(key, 0) + 1)
    loads = {}
    informed = False
    if 'harvest_loads' in messages:
        informed = True
        for key, value in messages['harvest_loads'].items():
            loads[str(key)] = max(0.0, value)
        if private_state.get('action', '') == 'harvest':
            key = str(private_state.get('target', society))
            loads[key] = max(
                0.0,
                loads.get(key, 0.0)
                - private_state.get('effort', 1.0)
            )
    else:
        for report in messages.get('reports', []):
            if report.get('member', -1) != member:
                informed = True
                message = report.get('message', {})
                if message.get('action', 'harvest') == 'harvest':
                    patch = message.get('target', message.get('patch', -1))
                    if patch != -1:
                        key = str(patch)
                        loads[key] = (
                            loads.get(key, 0.0)
                            + max(0.0, min(1.0, message.get('effort', 1.0)))
                        )
    chosen = society
    stock = 0.0
    effort = 0.0
    harvest_value = 0.0
    best_score = -1.0
    visible = []
    for patch in observation['patches']:
        patch_id = patch['id']
        patch_stock = max(0.0, patch['stock'])
        visible.append({'id': patch_id, 'stock': patch_stock})
        if informed:
            competition = (
                max(1.0, 0.5 * observation['n_members'])
                + 0.5 * loads.get(str(patch_id), 0.0)
            )
            if patch_id != society:
                competition += 0.2
        else:
            competition = max(1.0, 0.8 * observation['n_members'])
        patch_effort = min(1.0, patch_stock / max(0.01, capacity))
        expected_harvest = min(capacity, patch_stock / competition)
        value = expected_harvest * (1.0 - tax) - 0.08 * patch_effort
        score = value + 0.0001 * min(100.0, patch_stock)
        if patch_id == society:
            score += 0.00001
        if score > best_score:
            best_score = score
            chosen = patch_id
            stock = patch_stock
            effort = patch_effort
            harvest_value = value
    action = 'harvest' if effort > 0.0 else 'rest'
    target = chosen
    best_raid = -1.0
    raid_target = society
    if messages.get('raid_permission', True):
        societies = observation['n_societies']
        for offset in range(societies):
            other = (member + tick + offset) % societies
            if other != society:
                key = str(other)
                estimate = raid_values.get(key, 0.82)
                exploration = 0.10 / (1.0 + raid_counts.get(key, 0))
                value = estimate + exploration - 0.08
                if value > best_raid:
                    best_raid = value
                    raid_target = other
    if best_raid > max(0.0, harvest_value) + 0.18:
        action = 'raid'
        target = raid_target
        effort = 1.0
    return {
        'action': action,
        'target': target,
        'effort': effort,
        'message': {
            'patch': chosen,
            'stock': stock,
            'patches': visible,
            'action': action,
            'target': target,
            'effort': effort,
            'productivity': observation['productivity'],
            'wealth': wealth
        },
        'state': {
            'seen': private_state.get('seen', 0) + 1,
            'wealth': wealth,
            'action': action,
            'target': target,
            'effort': effort,
            'raid_values': raid_values,
            'raid_counts': raid_counts
        }
    }
def fill_buffers(forecasts, cash, ceiling):
    if not forecasts:
        return []
    needs = [max(0.0, ceiling - value) for value in forecasts]
    if sum(needs) <= cash:
        return needs
    lower = min(forecasts)
    upper = ceiling
    for iteration in range(18):
        level = 0.5 * (lower + upper)
        demand = sum(max(0.0, level - value) for value in forecasts)
        if demand > cash:
            upper = level
        else:
            lower = level
    return [max(0.0, lower - value) for value in forecasts]
def institution(observation, shared_state):
    members = observation['members']
    count = max(1, len(members))
    tick = observation['tick']
    treasury = max(0.0, observation['treasury'])
    infrastructure = max(0.0, observation['infrastructure'])
    tax = 0.78
    previous_people = shared_state.get('people', {})
    previous_tax = shared_state.get('tax', tax)
    previous_public = shared_state.get('public', 0.0)
    previous_defense = shared_state.get('defense', 0.0)
    previous_treasury = shared_state.get('treasury', 0.0)
    previous_pool = shared_state.get('pool', 2.4 * count * previous_tax)
    reports = {}
    stocks = []
    harvest_loads = {}
    for report in observation.get('reports', []):
        message = report.get('message', {})
        reports[str(report['member'])] = message
        best_stock = max(0.0, message.get('stock', 0.0))
        for patch in message.get('patches', []):
            best_stock = max(best_stock, patch['stock'])
        if 'stock' in message or message.get('patches', []):
            stocks.append(best_stock)
        if message.get('action', 'harvest') == 'harvest':
            patch = message.get('target', message.get('patch', -1))
            if patch != -1:
                key = str(patch)
                harvest_loads[key] = (
                    harvest_loads.get(key, 0.0)
                    + max(0.0, min(1.0, message.get('effort', 1.0)))
                )
    stock_availability = shared_state.get('availability', 1.0)
    if stocks:
        observed_availability = max(
            0.08,
            min(1.0, sum(stocks) / len(stocks) / (2.0 * count))
        )
        stock_availability = (
            0.35 * stock_availability + 0.65 * observed_availability
        )
    measured_pool = previous_pool
    measured = False
    if previous_people and previous_public > 0.000001:
        investment = 8.0 * count * (
            infrastructure
            - 0.96 * shared_state.get('infrastructure', infrastructure)
        )
        if investment >= -0.000001:
            measured_pool = min(
                max(8.0 * count, previous_treasury + 5.0 * count),
                max(0.0, investment) / previous_public
            )
            measured = True
    previous_redistribution = measured_pool * max(
        0.0, 1.0 - previous_public - previous_defense
    )
    observed_flow = max(0.0, measured_pool - previous_treasury)
    harvest_capacity = 0.0
    contributions = 0.0
    for member in members:
        key = str(member['id'])
        report = reports.get(key, {})
        action = report.get('action', 'harvest')
        effort = max(0.0, min(1.0, report.get('effort', 1.0)))
        if action == 'harvest':
            harvest_capacity += (
                2.4 * report.get('productivity', 1.0) * effort
            )
        elif action == 'contribute':
            prior_wealth = previous_people.get(key, {}).get(
                'wealth', member['wealth']
            )
            contributions += min(
                2.0 * effort, max(0.0, prior_wealth - 0.08 * effort)
            )
    realized_fraction = shared_state.get('availability', 1.0)
    if measured and previous_tax > 0.01 and harvest_capacity > 0.01:
        realized_fraction = max(
            0.0,
            min(
                1.0,
                (observed_flow - contributions)
                / (previous_tax * harvest_capacity)
            )
        )
        availability = (
            0.70 * realized_fraction + 0.30 * stock_availability
        )
    else:
        availability = stock_availability
    flow = shared_state.get('flow', 2.4 * count * previous_tax)
    if measured:
        flow = 0.30 * flow + 0.70 * observed_flow
        if observed_flow < 0.65 * flow:
            flow = min(flow, 1.10 * observed_flow + 0.10)
    baseline_flow = harvest_capacity * tax * availability + contributions
    expected_flow = (
        0.85 * flow * tax / max(0.05, previous_tax)
        + 0.15 * baseline_flow
    )
    pool = max(0.05, treasury + 0.96 * expected_flow)
    forecasts = []
    people = {}
    previous_transfers = {}
    loss_residual = 0.0
    for member in members:
        key = str(member['id'])
        wealth = max(0.0, member['wealth'])
        previous = previous_people.get(key, {})
        transfer = previous_redistribution * previous.get('share', 0.0)
        previous_transfers[key] = transfer
        report = reports.get(key, {})
        productivity = report.get('productivity', 1.0)
        effort = max(0.0, min(1.0, report.get('effort', 1.0)))
        action = report.get('action', 'harvest')
        capacity = 2.4 * productivity * effort
        model_income = (
            capacity * realized_fraction * (1.0 - previous_tax)
            - 0.85 - 0.08 * effort
        )
        if action == 'contribute' or action == 'share':
            prior_wealth = previous.get('wealth', wealth)
            payment = min(
                2.0 * effort, max(0.0, prior_wealth - 0.08 * effort)
            )
            model_income = -0.85 - 0.08 * effort - payment
        elif action == 'guard':
            model_income = -0.85 - 0.08 * effort
        elif action == 'rest':
            model_income = -0.85
        elif action == 'raid':
            model_income = 0.92 * effort - 0.85 - 0.08 * effort
        income = previous.get('income', model_income)
        risk = previous.get('risk', 0.35)
        if previous:
            observed_income = wealth - previous['wealth'] - transfer
            loss_residual += model_income - observed_income
            observed_income = max(-6.0, min(4.0, observed_income))
            risk = min(
                2.0,
                0.75 * risk + 0.25 * abs(observed_income - income)
            )
            income = 0.45 * income + 0.55 * observed_income
        if action == 'harvest':
            income += capacity * (
                availability * (1.0 - tax)
                - realized_fraction * (1.0 - previous_tax)
            )
        income = max(-5.0, min(3.0, income))
        forecasts.append(wealth + income - 0.20 - 0.25 * risk)
        people[key] = {
            'wealth': wealth,
            'income': income,
            'risk': risk,
            'share': 0.0
        }
    threat = shared_state.get('threat', 2.0)
    if previous_people and measured:
        previous_defense_cash = measured_pool * previous_defense
        observed_threat = max(0.0, loss_residual) * (
            (1.0 + previous_defense_cash)
            * (1.0 + 0.4 * previous_defense_cash)
        )
        threat = 0.80 * threat + 0.20 * min(12.0, observed_threat)
    defense_cash = 0.0
    best_cost = threat
    defense_limit = min(1.2, 0.20 * pool)
    for step in range(1, 13):
        cash = min(defense_limit, 0.10 * step)
        expected_loss = threat / (
            (1.0 + cash) * (1.0 + 0.4 * cash)
        )
        cost = cash + expected_loss
        if cost < best_cost:
            best_cost = cost
            defense_cash = cash
    remaining = max(1, 60 - tick)
    buffer = min(
        4.3 + 0.5 * (1.0 - availability),
        0.75 + 0.60 * remaining
    )
    desired_cash = sum(
        max(0.0, buffer - forecast) for forecast in forecasts
    )
    public_floor = 0.005
    redistribution_cash = min(
        desired_cash,
        max(0.0, pool * (1.0 - public_floor) - defense_cash)
    )
    weights = fill_buffers(forecasts, redistribution_cash, buffer)
    weight_sum = sum(weights)
    if weight_sum <= 0.0:
        weights = [1.0 for member in members]
        weight_sum = max(1.0, sum(weights))
    for index, member in enumerate(members):
        people[str(member['id'])]['share'] = weights[index] / weight_sum
    defense = defense_cash / pool
    public = max(
        public_floor,
        min(1.0 - defense, 1.0 - defense - redistribution_cash / pool)
    )
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
            'harvest_loads': harvest_loads,
            'buffer': buffer,
            'scarcity': availability < 0.7
        },
        'state': {
            'ticks': shared_state.get('ticks', 0) + 1,
            'people': people,
            'tax': tax,
            'public': public,
            'defense': defense,
            'pool': pool,
            'treasury': treasury,
            'infrastructure': infrastructure,
            'flow': flow,
            'availability': availability,
            'threat': threat
        }
    }
# EVOLVE-BLOCK-END
