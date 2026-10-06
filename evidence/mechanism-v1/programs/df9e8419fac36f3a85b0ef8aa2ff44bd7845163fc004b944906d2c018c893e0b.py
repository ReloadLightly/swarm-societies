"""Initial members harvest locally; a modest fixed tax funds infrastructure."""
# EVOLVE-BLOCK-START
def member_policy(observation, private_state):
    state = private_state or {}
    tick = observation['tick']
    society = observation['society_id']
    member = observation['member_id']
    wealth = max(0.0, observation['wealth'])
    capacity = 2.4 * observation['productivity']
    tax = min(0.8, max(0.0, observation['tax_rate']))
    patches = observation['patches']
    broadcast = observation.get('messages', {}) or {}
    societies = max(1, observation['n_societies'])
    members = max(1, observation['n_members'])
    loads = {}
    rebate = 0.0
    raids_allowed = True
    if broadcast.get('protocol') == 'waterline_1':
        loads = broadcast.get('loads', {})
        rebate = broadcast.get('rebates', {}).get(str(member), 0.0)
        raids_allowed = broadcast.get('raids', True)
    raid_return = state.get('raid_return', 0.70)
    raid_samples = state.get('raid_samples', 0)
    if state.get('action') == 'raid':
        previous_wealth = state.get('wealth', wealth)
        if previous_wealth >= 0.85 or wealth > 0.001:
            received = (
                wealth - previous_wealth + 0.85
                + state.get('cost', 0.08)
                - state.get('rebate', 0.0)
            )
            received = min(1.656, max(0.0, received))
            raid_return = 0.75 * raid_return + 0.25 * received
            raid_samples = min(100, raid_samples + 1)
    action = 'rest'
    target = society
    effort = 0.0
    best_score = 0.0
    for index, patch in enumerate(patches):
        stock = max(0.0, patch['stock'])
        patch_id = patch['id']
        competing = 0.5 * max(1, members - 1)
        if str(patch_id) in loads:
            other_load = loads[str(patch_id)]
            if (
                state.get('action') == 'harvest'
                and state.get('target') == patch_id
            ):
                other_load = max(
                    0.0,
                    other_load - state.get('capacity', capacity)
                    * state.get('effort', 1.0)
                )
            competing = 1.0 + other_load / max(0.1, capacity)
        available = stock / (1.0 + 0.55 * competing)
        expected_yield = min(capacity, available)
        harvest_effort = min(1.0, stock / max(0.1, capacity))
        net_return = (
            expected_yield * (1.0 - tax)
            - 0.08 * harvest_effort
        )
        preference = 0.0
        if expected_yield > 0.05:
            preference = 0.02 * min(
                1.0, stock / max(0.1, 4.0 * capacity)
            )
            preference += 0.002 * (
                (tick + member + index) % max(1, len(patches))
            )
        score = net_return + preference
        if score > best_score:
            best_score = score
            action = 'harvest'
            target = patch_id
            effort = harvest_effort
    if societies > 1 and raids_allowed:
        uncertainty_discount = 0.15 if raid_samples < 3 else 0.05
        raid_score = max(0.0, raid_return - 0.08 - uncertainty_discount)
        if raid_score > best_score + 0.08:
            action = 'raid'
            target = (
                society + 1 + (tick + member) % (societies - 1)
            ) % societies
            effort = 1.0
    report_patches = []
    for patch in patches:
        report_patches.append([
            patch['id'], round(max(0.0, patch['stock']), 3)
        ])
    return {
        'action': action,
        'target': target,
        'effort': effort,
        'message': {
            'protocol': 'waterline_1',
            'patches': report_patches,
            'action': action,
            'target': target,
            'effort': round(effort, 4),
            'capacity': round(capacity, 4)
        },
        'state': {
            'action': action,
            'target': target,
            'effort': effort,
            'capacity': capacity,
            'wealth': wealth,
            'cost': min(wealth, 0.08 * effort),
            'rebate': rebate,
            'raid_return': raid_return,
            'raid_samples': raid_samples
        }
    }
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
        member_key = str(report['member'])
        if message.get('protocol') == 'waterline_1':
            reports[member_key] = message
            for patch in message.get('patches', []):
                patch_key = str(patch[0])
                stock = max(0.0, patch[1])
                stocks[patch_key] = max(
                    stock, stocks.get(patch_key, 0.0)
                )
            if message.get('action') == 'harvest':
                patch_key = str(message['target'])
                load = (
                    message.get('capacity', 2.4)
                    * message.get('effort', 1.0)
                )
                loads[patch_key] = loads.get(patch_key, 0.0) + load
        elif 'patch' in message and 'stock' in message:
            patch_key = str(message['patch'])
            stocks[patch_key] = max(
                max(0.0, message['stock']),
                stocks.get(patch_key, 0.0)
            )
            loads[patch_key] = loads.get(patch_key, 0.0) + 2.4
    wealths = [max(0.0, member['wealth']) for member in members]
    liquid = treasury + sum(wealths)
    mean_wealth = sum(wealths) / count
    scarcity = state.get('scarcity', 0.0)
    if stocks:
        average_stock = sum(stocks.values()) / len(stocks)
        stock_buffer = 4.8 * count
        observed_scarcity = min(
            1.0, max(0.0, 1.0 - average_stock / stock_buffer)
        )
        scarcity = 0.35 * scarcity + 0.65 * observed_scarcity
    income = state.get('income', 2.1 * count)
    liquid_change = 0.0
    if 'liquid' in state:
        liquid_change = liquid - state['liquid']
        observed_income = (
            liquid_change + 0.93 * count
            + state.get('spending', 0.0)
        )
        observed_income = min(
            2.76 * count, max(0.0, observed_income)
        )
        income = 0.7 * income + 0.3 * observed_income
    shortage = sum(max(0.0, 1.7 - value) for value in wealths)
    shortage /= 1.7 * count
    inequality = min(
        1.0,
        (max(wealths) - min(wealths)) / max(2.0, mean_wealth + 1.0)
    )
    tax = min(
        0.68,
        0.40 + 0.18 * scarcity + 0.10 * shortage + 0.06 * inequality
    )
    harvests = []
    contributions = 0.0
    fallback_harvest = min(
        2.4, max(0.2, income / count)
    )
    for member in members:
        message = reports.get(str(member['id']), {})
        harvest = fallback_harvest
        reported_action = message.get('action')
        if reported_action == 'harvest':
            capacity = message.get('capacity', 2.4)
            effort = message.get('effort', 1.0)
            patch_key = str(message.get('target'))
            stock = stocks.get(patch_key, 2.4 * count)
            other_load = max(
                0.0,
                loads.get(patch_key, capacity) - capacity * effort
            )
            congestion = 1.5 + 0.45 * other_load / max(0.1, capacity)
            harvest = min(capacity * effort, stock / congestion)
        elif reported_action:
            harvest = 0.0
            if reported_action == 'contribute':
                contributions += min(
                    max(0.0, member['wealth']),
                    2.0 * message.get('effort', 1.0)
                )
        harvests.append(max(0.0, harvest))
    pool = treasury + tax * sum(harvests) + contributions
    drawdown = min(
        1.0, max(0.0, -liquid_change / max(1.0, 0.85 * count))
    )
    infrastructure_target = 0.85 + 0.65 * scarcity + 0.20 * drawdown
    desired_investment = 8.0 * count * max(
        0.0,
        0.04 * infrastructure
        + 0.16 * (infrastructure_target - infrastructure)
    )
    buffer_target = count * (2.55 + 1.25 * scarcity)
    projected_liquid = liquid + income - 0.93 * count
    surplus = max(0.0, projected_liquid - buffer_target)
    immediate_needs = sum(
        max(0.0, 1.05 - value) for value in wealths
    )
    available_for_investment = max(0.0, pool - immediate_needs)
    investment = min(
        desired_investment,
        0.60 * pool,
        0.35 * surplus,
        available_for_investment
    )
    public_fraction = investment / pool if pool > 0.001 else 0.0
    distribution_budget = max(0.0, pool - investment)
    projected_holdings = []
    for index, wealth in enumerate(wealths):
        cautious_income = 0.35 * (1.0 - tax) * harvests[index]
        projected_holdings.append(
            max(0.0, wealth + cautious_income - 0.08)
        )
    lower = min(projected_holdings)
    upper = max(projected_holdings) + distribution_budget + 1.0
    for iteration in range(20):
        level = 0.5 * (lower + upper)
        required = sum(
            max(0.0, level - holding)
            for holding in projected_holdings
        )
        if required > distribution_budget:
            upper = level
        else:
            lower = level
    waterline = 0.5 * (lower + upper)
    weights = [
        max(0.0, waterline - holding)
        for holding in projected_holdings
    ]
    if sum(weights) < 0.0001:
        weights = [
            1.0 / (0.25 + holding)
            for holding in projected_holdings
        ]
    weight_total = sum(weights)
    rebates = {}
    for index, member in enumerate(members):
        rebates[str(member['id'])] = round(
            distribution_budget * weights[index] / weight_total, 4
        )
    return {
        'tax_rate': tax,
        'public_fraction': public_fraction,
        'defense_fraction': 0.0,
        'reserve_fraction': 0.0,
        'redistribution': weights,
        'raid_permission': True,
        'messages': {
            'protocol': 'waterline_1',
            'loads': loads,
            'rebates': rebates,
            'raids': True
        },
        'state': {
            'liquid': liquid,
            'income': income,
            'scarcity': scarcity,
            'spending': investment
        }
    }
# EVOLVE-BLOCK-END
