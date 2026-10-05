"""Initial members harvest locally; a modest fixed tax funds infrastructure."""
# EVOLVE-BLOCK-START
def member_policy(observation, private_state):
    tick = observation['tick']
    society = observation['society_id']
    member = observation['member_id']
    wealth = max(0.0, observation['wealth'])
    societies = observation['n_societies']
    count = max(1, observation['n_members'])
    capacity = 2.4 * observation['productivity']
    tax = observation['tax_rate']
    messages = observation.get('messages', {})
    raid_values = {}
    raid_counts = {}
    raid_times = {}
    for other in range(societies):
        key = str(other)
        raid_values[key] = private_state.get(
            'raid_values', {}
        ).get(key, 0.90)
        raid_counts[key] = 0.97 * private_state.get(
            'raid_counts', {}
        ).get(key, 0.0)
        raid_times[key] = private_state.get(
            'raid_times', {}
        ).get(key, tick)
    if private_state.get('action', '') == 'raid':
        key = str(private_state.get('target', society))
        previous_wealth = private_state.get('wealth', wealth)
        previous_effort = private_state.get('effort', 1.0)
        transfer = messages.get(
            'previous_transfers', {}
        ).get(str(member), 0.0)
        reward = (
            wealth - previous_wealth + 0.85
            + min(previous_wealth, 0.08 * previous_effort)
            - transfer
        )
        reward = max(0.0, min(1.656, reward))
        if wealth <= 0.001:
            reward = 0.0
        samples = raid_counts.get(key, 0.0)
        learning_rate = 0.22 + 0.25 / (1.0 + samples)
        raid_values[key] = (
            (1.0 - learning_rate) * raid_values.get(key, 0.90)
            + learning_rate * reward
        )
        raid_counts[key] = min(60.0, samples + 1.0)
        raid_times[key] = tick
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
                message = report.get('message', {})
                if message.get('action', 'harvest') == 'harvest':
                    patch = message.get(
                        'target', message.get('patch', -1)
                    )
                    if patch != -1:
                        informed = True
                        key = str(patch)
                        loads[key] = loads.get(key, 0.0) + max(
                            0.0, min(1.0, message.get('effort', 1.0))
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
        competition = max(1.0, 0.8 * count)
        if informed:
            competition = max(
                1.0, 0.55 * count
                + 0.55 * loads.get(str(patch_id), 0.0)
            )
            if patch_id != society:
                competition += 0.15
        patch_effort = min(
            1.0, patch_stock / max(0.01, capacity)
        )
        expected_harvest = min(
            capacity * patch_effort, patch_stock / competition
        )
        value = (
            expected_harvest * (1.0 - tax)
            - min(wealth, 0.08 * patch_effort)
        )
        score = value + 0.0001 * min(100.0, patch_stock)
        if patch_id == society:
            score += 0.00001
        if score > best_score:
            best_score = score
            chosen = patch_id
            stock = patch_stock
            effort = patch_effort
            harvest_value = value
    action = 'harvest'
    target = chosen
    if effort <= 0.0 or harvest_value <= 0.0:
        action = 'rest'
        effort = 0.0
        harvest_value = 0.0
    defense_cash = max(0.0, messages.get('defense_cash', 0.0))
    peer_prior = 1.242 / (
        (1.0 + defense_cash) * (1.0 + 0.4 * defense_cash)
    )
    peer_resources = []
    for key, value in messages.get('wealths', {}).items():
        if str(key) != str(member):
            peer_resources.append(min(2.3, max(0.0, value)))
    if peer_resources:
        peer_prior *= min(
            1.0, sum(peer_resources) / (2.3 * len(peer_resources))
        )
    remaining = max(1, 60 - tick)
    food_risk = 0.22 * max(0.0, 1.5 - wealth) / 1.5
    best_raid = -1.0
    raid_target = society
    external_allowed = messages.get('raid_permission', True)
    for offset in range(societies):
        other = (member + tick + offset) % societies
        if other == society or external_allowed:
            key = str(other)
            prior = peer_prior if other == society else 0.86
            samples = raid_counts.get(key, 0.0)
            confidence = samples / (samples + 2.0)
            estimate = (
                confidence * raid_values.get(key, prior)
                + (1.0 - confidence) * prior
            )
            age = max(0, tick - raid_times.get(key, tick))
            exploration = min(1.0, remaining / 12.0) * (
                0.14 / (1.0 + 0.5 * samples)
                + 0.04 * min(1.0, age / 12.0)
            )
            value = (
                min(1.656, estimate + exploration)
                - min(wealth, 0.08) - food_risk
            )
            if value > best_raid:
                best_raid = value
                raid_target = other
    switch_margin = 0.10
    if remaining <= 5:
        switch_margin = 0.04
    if best_raid > harvest_value + switch_margin:
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
            'wealth': wealth,
            'action': action,
            'target': target,
            'effort': effort,
            'raid_values': raid_values,
            'raid_counts': raid_counts,
            'raid_times': raid_times
        }
    }
def fill_buffers(forecasts, cash, ceiling):
    if not forecasts:
        return []
    needs = [max(0.0, ceiling - value) for value in forecasts]
    cash = max(0.0, cash)
    if sum(needs) <= cash:
        return needs
    if cash <= 0.0:
        return [0.0 for value in forecasts]
    ordered = sorted(forecasts)
    level = ordered[0]
    active = 1
    for index in range(1, len(ordered)):
        next_level = min(ceiling, ordered[index])
        cost = max(0.0, next_level - level) * active
        if cash <= cost:
            level += cash / active
            cash = 0.0
            break
        cash -= cost
        level = next_level
        active += 1
        if level >= ceiling:
            break
    if cash > 0.0:
        level = min(ceiling, level + cash / active)
    return [max(0.0, level - value) for value in forecasts]
def institution(observation, shared_state):
    members = observation['members']
    count = max(1, len(members))
    tick = observation['tick']
    treasury = max(0.0, observation['treasury'])
    infrastructure = max(0.0, observation['infrastructure'])
    tax = 0.80
    previous_people = shared_state.get('people', {})
    previous_tax = shared_state.get('tax', tax)
    previous_public = shared_state.get('public', 0.0)
    previous_defense = shared_state.get('defense', 0.0)
    previous_treasury = shared_state.get('treasury', 0.0)
    previous_pool = shared_state.get(
        'pool', 2.4 * count * previous_tax
    )
    reports = {}
    stocks = []
    harvest_loads = {}
    for report in observation.get('reports', []):
        message = report.get('message', {})
        reports[str(report['member'])] = message
        best_stock = max(0.0, message.get('stock', 0.0))
        visible = message.get('patches', [])
        for patch in visible:
            best_stock = max(best_stock, max(0.0, patch['stock']))
        if 'stock' in message or visible:
            stocks.append(best_stock)
        if message.get('action', 'harvest') == 'harvest':
            patch = message.get('target', message.get('patch', -1))
            if patch != -1:
                key = str(patch)
                harvest_loads[key] = harvest_loads.get(key, 0.0) + max(
                    0.0, min(1.0, message.get('effort', 1.0))
                )
    stock_availability = shared_state.get('availability', 1.0)
    if stocks:
        observed_availability = max(
            0.03,
            min(1.0, sum(stocks) / (len(stocks) * 2.0 * count))
        )
        stock_availability = (
            0.45 * stock_availability + 0.55 * observed_availability
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
                previous_treasury + 6.0 * count,
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
            old_wealth = previous_people.get(key, {}).get(
                'wealth', member['wealth']
            )
            contributions += min(
                2.0 * effort, max(0.0, old_wealth - 0.08 * effort)
            )
    realized_fraction = shared_state.get('availability', 1.0)
    availability = stock_availability
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
            0.85 * realized_fraction + 0.15 * stock_availability
        )
    flow = shared_state.get('flow', 2.4 * count * previous_tax)
    volatility = shared_state.get('volatility', 0.20)
    if measured:
        prediction_error = abs(
            observed_flow - shared_state.get('expected_flow', flow)
        )
        volatility = min(
            4.0, 0.75 * volatility + 0.25 * prediction_error
        )
        if observed_flow < 0.72 * flow:
            flow = 0.15 * flow + 0.85 * observed_flow
        else:
            flow = 0.35 * flow + 0.65 * observed_flow
    baseline_flow = harvest_capacity * tax * availability + contributions
    expected_flow = max(
        0.0,
        0.80 * flow * tax / max(0.05, previous_tax)
        + 0.20 * baseline_flow
    )
    pool = max(
        0.02,
        treasury + max(0.0, 0.98 * expected_flow - 0.25 * volatility)
    )
    forecasts = []
    people = {}
    previous_transfers = {}
    wealths = {}
    loss_residual = 0.0
    for member in members:
        key = str(member['id'])
        wealth = max(0.0, member['wealth'])
        wealths[key] = wealth
        previous = previous_people.get(key, {})
        old_wealth = previous.get('wealth', wealth)
        transfer = previous_redistribution * previous.get('share', 0.0)
        previous_transfers[key] = transfer
        report = reports.get(key, {})
        action = report.get('action', 'harvest')
        effort = max(0.0, min(1.0, report.get('effort', 1.0)))
        capacity = 2.4 * report.get('productivity', 1.0) * effort
        cost = min(old_wealth, 0.08 * effort)
        model_income = (
            capacity * realized_fraction * (1.0 - previous_tax)
            - 0.85 - cost
        )
        if action == 'contribute' or action == 'share':
            payment = min(
                2.0 * effort, max(0.0, old_wealth - cost)
            )
            model_income = -0.85 - cost - payment
        elif action == 'guard':
            model_income = -0.85 - cost
        elif action == 'rest':
            model_income = -0.85
        elif action == 'raid':
            model_income = 0.85 * effort - 0.85 - cost
        income = previous.get('income', model_income)
        risk = previous.get('risk', 0.20)
        if previous:
            observed_income = wealth - old_wealth - transfer
            loss_residual += model_income - observed_income
            observed_income = max(-6.0, min(4.0, observed_income))
            risk = min(
                2.5,
                0.70 * risk + 0.30 * abs(observed_income - income)
            )
            income = 0.45 * income + 0.55 * observed_income
        if action == 'harvest':
            income += capacity * (
                availability * (1.0 - tax)
                - realized_fraction * (1.0 - previous_tax)
            )
        income = max(-5.0, min(3.0, income))
        forecasts.append(wealth + income - 0.12 - 0.35 * risk)
        people[key] = {
            'wealth': wealth,
            'income': income,
            'risk': risk,
            'share': 0.0
        }
    threat = shared_state.get('threat', 0.25)
    if previous_people and measured:
        old_defense_cash = measured_pool * previous_defense
        observed_threat = max(
            0.0, loss_residual - 0.05 * count
        ) * (
            (1.0 + old_defense_cash)
            * (1.0 + 0.4 * old_defense_cash)
        )
        threat = 0.72 * threat + 0.28 * min(12.0, observed_threat)
    public_floor = 0.005
    emergency_cash = sum(max(0.0, -value) for value in forecasts)
    defense_limit = min(
        1.8,
        0.28 * pool,
        max(0.0, pool * (1.0 - public_floor) - emergency_cash)
    )
    defense_cash = 0.0
    best_cost = threat
    for step in range(1, 19):
        cash = min(defense_limit, 0.10 * step)
        expected_loss = threat / (
            (1.0 + cash) * (1.0 + 0.4 * cash)
        )
        cost = cash + expected_loss
        if cost < best_cost:
            best_cost = cost
            defense_cash = cash
    remaining = max(1, 60 - tick)
    buffer = (
        1.25
        + 0.65 * (1.0 - availability)
        + min(1.45, 0.80 * threat / (1.0 + defense_cash))
        + 0.20 * min(1.5, volatility)
    )
    buffer = min(
        buffer,
        0.25 + 0.55 * remaining + min(1.2, 0.50 * threat)
    )
    desired_cash = sum(
        max(0.0, buffer - value) for value in forecasts
    )
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
        public_floor, 1.0 - defense - redistribution_cash / pool
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
            'wealths': wealths,
            'defense_cash': defense_cash,
            'buffer': buffer,
            'scarcity': availability < 0.72
        },
        'state': {
            'people': people,
            'tax': tax,
            'public': public,
            'defense': defense,
            'pool': pool,
            'treasury': treasury,
            'infrastructure': infrastructure,
            'flow': flow,
            'expected_flow': expected_flow,
            'volatility': volatility,
            'availability': availability,
            'threat': threat
        }
    }
# EVOLVE-BLOCK-END
