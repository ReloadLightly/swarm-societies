"""Initial members harvest locally; a modest fixed tax funds infrastructure."""
# EVOLVE-BLOCK-START
def member_policy(observation, private_state):
    tick = observation['tick']
    society = observation['society_id']
    member = observation['member_id']
    wealth = observation['wealth']
    patches = observation['patches']
    messages = observation.get('messages', {})
    capacity = 2.4 * observation['productivity']
    tax = observation['tax_rate']
    raid_values = private_state.get('raid_values', {}).copy()
    raid_counts = private_state.get('raid_counts', {}).copy()
    if private_state.get('action', '') == 'raid':
        previous_target = str(private_state.get('target', society))
        transfers = messages.get('previous_transfers', {})
        transfer = transfers.get(str(member), 0.0)
        reward = (
            wealth - private_state.get('wealth', wealth)
            + 0.85 + 0.08 * private_state.get('effort', 1.0)
            - transfer
        )
        reward = max(0.0, min(1.65, reward))
        if wealth <= 0.01:
            reward = 0.0
        old_value = raid_values.get(previous_target, 0.82)
        raid_values[previous_target] = 0.65 * old_value + 0.35 * reward
        raid_counts[previous_target] = min(
            60, raid_counts.get(previous_target, 0) + 1
        )
    chosen = society
    stock = 0.0
    visible = []
    for patch in patches:
        patch_stock = max(0.0, patch['stock'])
        visible.append({'id': patch['id'], 'stock': patch_stock})
        if patch_stock > stock:
            chosen = patch['id']
            stock = patch_stock
        elif patch_stock == stock and patch['id'] == society:
            chosen = patch['id']
    effort = min(1.0, stock / max(0.01, capacity))
    action = 'harvest' if effort > 0.0 else 'rest'
    target = chosen
    competition = max(1.0, 0.8 * observation['n_members'])
    expected_harvest = min(capacity, stock / competition)
    harvest_value = expected_harvest * (1.0 - tax) - 0.08 * effort
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
def institution(observation, shared_state):
    members = observation['members']
    count = max(1, len(members))
    tick = observation['tick']
    treasury = max(0.0, observation['treasury'])
    infrastructure = max(0.0, observation['infrastructure'])
    tax = 0.66
    reports = {}
    stocks = []
    for report in observation.get('reports', []):
        message = report.get('message', {})
        reports[str(report['member'])] = message
        if 'stock' in message:
            stocks.append(max(0.0, message['stock']))
    availability = shared_state.get('availability', 1.0)
    if stocks:
        observed_availability = min(
            1.0, max(0.12, sum(stocks) / len(stocks) / (2.0 * count))
        )
        availability = (
            0.35 * availability + 0.65 * observed_availability
        )
    previous_people = shared_state.get('people', {})
    previous_tax = shared_state.get('tax', tax)
    previous_public = shared_state.get('public', 0.0)
    previous_defense = shared_state.get('defense', 0.0)
    previous_pool = shared_state.get('pool', 2.25 * count * tax)
    measured_pool = previous_pool
    measured = False
    if previous_people and previous_public > 0.05:
        investment = 8.0 * count * (
            infrastructure
            - 0.96 * shared_state.get('infrastructure', infrastructure)
        )
        if investment >= 0.0:
            measured_pool = min(
                6.0 * count, investment / previous_public
            )
            measured = True
    previous_redistribution = measured_pool * max(
        0.0, 1.0 - previous_public - previous_defense
    )
    flow = shared_state.get('flow', 2.25 * count * tax)
    if measured:
        observed_flow = max(
            0.0, measured_pool - shared_state.get('treasury', 0.0)
        )
        flow = 0.55 * flow + 0.45 * observed_flow
    baseline_flow = 2.25 * count * tax * availability
    expected_flow = 0.55 * flow + 0.45 * baseline_flow
    if availability < 0.7:
        expected_flow = min(expected_flow, 1.15 * baseline_flow)
    pool = max(0.05, treasury + expected_flow)
    remaining = max(1, 60 - tick)
    buffer = min(
        3.6 + 0.8 * (1.0 - availability),
        2.5 + 0.25 * remaining
    )
    forecasts = []
    people = {}
    previous_transfers = {}
    total_loss = 0.0
    for member in members:
        key = str(member['id'])
        wealth = max(0.0, member['wealth'])
        previous = previous_people.get(key, {})
        transfer = previous_redistribution * previous.get('share', 0.0)
        previous_transfers[key] = transfer
        report = reports.get(key, {})
        productivity = report.get('productivity', 0.9375)
        expected_income = (
            2.4 * productivity * availability * (1.0 - previous_tax)
            - 0.93
        )
        reported_action = report.get('action', 'harvest')
        if reported_action == 'contribute' or reported_action == 'share':
            expected_income = -0.85 - 2.08 * report.get('effort', 1.0)
        elif reported_action == 'guard':
            expected_income = -0.85 - 0.08 * report.get('effort', 1.0)
        elif reported_action == 'rest':
            expected_income = -0.85
        elif reported_action == 'raid':
            expected_income = 0.1
        income = previous.get('income', expected_income)
        if previous:
            observed_income = wealth - previous['wealth'] - transfer
            observed_income = max(-4.0, min(3.0, observed_income))
            income = 0.55 * income + 0.45 * observed_income
            total_loss += max(0.0, expected_income - observed_income)
        income += (
            2.4 * productivity * availability * (previous_tax - tax)
        )
        income = max(-3.5, min(2.0, income))
        forecast = wealth + income - 0.2
        forecasts.append(forecast)
        people[key] = {
            'wealth': wealth,
            'income': income,
            'share': 0.0
        }
    loss = shared_state.get('loss', 1.0)
    if previous_people:
        loss = 0.75 * loss + 0.25 * min(5.0, total_loss)
    defense_cash = min(0.6, 0.26 * loss)
    defense = min(0.12, defense_cash / pool)
    needs = [max(0.0, buffer - forecast) for forecast in forecasts]
    desired_cash = sum(needs)
    redistribution_cash = min(
        desired_cash, pool * (1.0 - defense)
    )
    weights = needs
    if desired_cash > redistribution_cash and forecasts:
        lower = min(forecasts)
        upper = buffer
        for iteration in range(16):
            level = 0.5 * (lower + upper)
            demand = sum(
                max(0.0, level - forecast) for forecast in forecasts
            )
            if demand > redistribution_cash:
                upper = level
            else:
                lower = level
        weights = [
            max(0.0, lower - forecast) for forecast in forecasts
        ]
    weight_sum = sum(weights)
    if weight_sum <= 0.0:
        weights = [1.0 for member in members]
        weight_sum = max(1.0, sum(weights))
    for index, member in enumerate(members):
        people[str(member['id'])]['share'] = weights[index] / weight_sum
    public = max(
        0.0, 1.0 - defense - redistribution_cash / pool
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
            'loss': loss
        }
    }
# EVOLVE-BLOCK-END
