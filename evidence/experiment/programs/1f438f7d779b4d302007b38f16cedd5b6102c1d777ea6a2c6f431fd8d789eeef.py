"""Initial members harvest locally; a modest fixed tax funds infrastructure."""
# EVOLVE-BLOCK-START
def waterfill(projected, budget, target):
    needs = [max(0.0, target - value) for value in projected]
    if sum(needs) <= budget:
        return needs
    if budget <= 0.0 or not projected:
        return [0.0 for value in projected]
    lower = min(projected)
    upper = target
    for step in range(14):
        middle = (lower + upper) * 0.5
        required = sum(max(0.0, middle - value) for value in projected)
        if required <= budget:
            lower = middle
        else:
            upper = middle
    return [max(0.0, lower - value) for value in projected]
def member_policy(observation, private_state):
    memory = private_state or {}
    tick = observation['tick']
    society = observation['society_id']
    member = observation['member_id']
    wealth = observation['wealth']
    productivity = observation['productivity']
    capacity = max(0.01, 2.4 * productivity)
    tax = max(0.0, min(0.8, observation['tax_rate']))
    patches = observation['patches']
    broadcast = observation.get('messages', {})
    claims = {}
    grant = 0.0
    if broadcast.get('flow_controller', 0) == 1:
        claims = broadcast.get('claims', {})
        grant = broadcast.get('aid', {}).get(str(member), 0.0)
    quality = memory.get('quality', {}).copy()
    previous = memory.get('previous', {})
    if previous.get('tick', -2) == tick - 1:
        if previous.get('action', 'rest') == 'harvest':
            retained = max(0.2, 1.0 - previous.get('tax', tax))
            recovered = (
                wealth - previous.get('wealth', wealth)
                + 0.85 + 0.08 * previous.get('effort', 1.0)
                - previous.get('grant', 0.0)
            ) / retained
            expected = max(0.1, previous.get('gross', capacity))
            reliability = max(0.35, min(1.0, recovered / expected))
            key = str(previous.get('target', society))
            old_quality = quality.get(key, 1.0)
            quality[key] = 0.8 * old_quality + 0.2 * reliability
    action = 'rest'
    target = society
    effort = 0.0
    selected_stock = 0.0
    selected_gross = 0.0
    best_score = 0.0
    visible = []
    peers = max(0, observation.get('n_members', 4) - 1)
    for index, patch in enumerate(patches):
        patch_id = patch['id']
        stock = max(0.0, patch['stock'])
        key = str(patch_id)
        visible.append([patch_id, stock])
        pressure = 1.0 + 0.5 * peers
        if claims:
            pressure = (
                1.0 + 0.25 * peers
                + 0.5 * max(0.0, claims.get(key, 1.0) - 1.0)
            )
        expected_gross = min(capacity, stock / (1.0 + pressure))
        proposed_effort = min(1.0, stock / capacity)
        reliability = quality.get(key, 1.0)
        expected_return = (
            (1.0 - tax) * expected_gross * (0.85 + 0.15 * reliability)
            - 0.08 * proposed_effort
        )
        phase = (tick * 7 + member * 11 + society * 3 + index * 13) % 23
        score = expected_return + 0.025 * phase / 23.0
        if expected_return > 0.002 and score > best_score:
            best_score = score
            action = 'harvest'
            target = patch_id
            effort = proposed_effort
            selected_stock = stock
            selected_gross = expected_gross
    return {
        'action': action,
        'target': target,
        'effort': effort,
        'message': {
            'flow_controller': 1,
            'patch': target,
            'stock': selected_stock,
            'action': action,
            'effort': effort,
            'productivity': productivity,
            'visible': visible
        },
        'state': {
            'quality': quality,
            'previous': {
                'tick': tick,
                'action': action,
                'target': target,
                'wealth': wealth,
                'tax': tax,
                'effort': effort,
                'gross': selected_gross,
                'grant': grant
            }
        }
    }
def institution(observation, shared_state):
    memory = shared_state or {}
    tick = observation['tick']
    members = observation['members']
    count = len(members)
    treasury = max(0.0, observation['treasury'])
    if count == 0:
        return {
            'tax_rate': 0.0,
            'public_fraction': 1.0,
            'defense_fraction': 0.0,
            'reserve_fraction': 0.0,
            'redistribution': [],
            'raid_permission': False,
            'messages': {},
            'state': {}
        }
    reports = {}
    for report in observation.get('reports', []):
        reports[str(report['member'])] = report.get('message', {})
    claims = {}
    for member in members:
        report = reports.get(str(member['id']), {})
        if 'patch' in report:
            if report.get('action', 'harvest') == 'harvest':
                key = str(report['patch'])
                claims[key] = claims.get(key, 0.0) + 1.0
    previous_harvest = memory.get('harvest', {})
    next_harvest = {}
    harvest = []
    costs = []
    wealth = []
    total_capacity = 0.0
    for member in members:
        key = str(member['id'])
        report = reports.get(key, {})
        own_format = report.get('flow_controller', 0) == 1
        productivity = report.get('productivity', 1.0) if own_format else 1.0
        capacity = max(0.1, 2.4 * productivity)
        total_capacity += capacity
        current_wealth = max(0.0, member['wealth'])
        wealth.append(current_wealth)
        raw_harvest = capacity
        if 'stock' in report:
            stock = max(0.0, report['stock'])
            patch_key = str(report.get('patch', observation['society_id']))
            competitors = 1.0 + claims.get(patch_key, 1.0)
            raw_harvest = min(capacity, stock / max(1.0, competitors))
        operating_cost = 0.93
        if own_format:
            reported_action = report.get('action', 'harvest')
            reported_effort = max(0.0, min(1.0, report.get('effort', 1.0)))
            operating_cost = 0.85 + 0.08 * reported_effort
            if reported_action != 'harvest':
                raw_harvest = 0.0
            if reported_action == 'rest':
                operating_cost = 0.85
            if reported_action in ['contribute', 'share']:
                operating_cost += min(
                    2.0 * reported_effort,
                    max(0.0, current_wealth - 1.0)
                )
        old_harvest = previous_harvest.get(key, raw_harvest)
        learning_rate = 0.65 if raw_harvest < old_harvest else 0.25
        estimate = (
            learning_rate * raw_harvest
            + (1.0 - learning_rate) * old_harvest
        )
        next_harvest[key] = estimate
        harvest.append(0.9 * estimate)
        costs.append(operating_cost)
    total_harvest = sum(harvest)
    scarcity = max(0.0, min(1.0, 1.0 - total_harvest / total_capacity))
    previous_total = memory.get('gross', total_harvest)
    disturbance = min(0.8, abs(total_harvest - previous_total) / count)
    remaining = max(0, 59 - tick)
    buffer = min(
        2.4 + 1.6 * scarcity + disturbance,
        0.85 * remaining
    )
    unexplained_loss = max(
        0.0,
        memory.get('expected_total', sum(wealth)) - sum(wealth) - 0.2 * count
    )
    loss_memory = memory.get('loss', 0.0)
    if scarcity < 0.3:
        loss_memory = 0.75 * loss_memory + 0.25 * unexplained_loss
    else:
        loss_memory *= 0.6
    best_score = -1000000.0
    best_tax = 0.2
    best_budget = 0.0
    best_defense = 0.0
    best_investment = 0.0
    best_grants = [0.0 for member in members]
    best_projected = wealth
    old_tax = memory.get('tax', 0.5)
    for tax in [0.2, 0.35, 0.5, 0.6, 0.7, 0.8]:
        budget = treasury + tax * total_harvest
        defense = min(
            0.12 * budget,
            0.25 * max(0.0, loss_memory - 0.8)
        )
        spendable = max(0.0, budget - defense)
        projected = [
            wealth[index] + (1.0 - tax) * harvest[index] - costs[index]
            for index in range(count)
        ]
        grants = waterfill(projected, spendable, buffer)
        investment = max(0.0, spendable - sum(grants))
        final_balances = [
            projected[index] + grants[index]
            for index in range(count)
        ]
        shortfall = sum(max(0.0, -value) for value in final_balances)
        buffer_gap = sum(max(0.0, buffer - value) for value in final_balances)
        score = (
            investment
            - 12.0 * shortfall
            - 0.3 * buffer_gap
            - 0.045 * count * tax
            - 0.015 * count * abs(tax - old_tax)
        )
        if score > best_score:
            best_score = score
            best_tax = tax
            best_budget = budget
            best_defense = defense
            best_investment = investment
            best_grants = grants
            best_projected = projected
    if best_budget > 0.000001:
        defense_fraction = best_defense / best_budget
        public_fraction = min(
            1.0 - defense_fraction,
            best_investment / best_budget
        )
    else:
        defense_fraction = 0.0
        public_fraction = 0.0
    redistribution = best_grants
    if sum(redistribution) <= 0.000001:
        redistribution = [
            max(0.01, buffer - value)
            for value in best_projected
        ]
    aid = {}
    expected_total = 0.0
    for index, member in enumerate(members):
        aid[str(member['id'])] = best_grants[index]
        expected_total += max(
            0.0, best_projected[index] + best_grants[index]
        )
    return {
        'tax_rate': best_tax,
        'public_fraction': max(0.0, public_fraction),
        'defense_fraction': defense_fraction,
        'reserve_fraction': 0.0,
        'redistribution': redistribution,
        'raid_permission': False,
        'messages': {
            'flow_controller': 1,
            'claims': claims,
            'aid': aid,
            'scarcity': scarcity,
            'buffer': buffer
        },
        'state': {
            'harvest': next_harvest,
            'gross': total_harvest,
            'expected_total': expected_total,
            'loss': loss_memory,
            'tax': best_tax
        }
    }
# EVOLVE-BLOCK-END
