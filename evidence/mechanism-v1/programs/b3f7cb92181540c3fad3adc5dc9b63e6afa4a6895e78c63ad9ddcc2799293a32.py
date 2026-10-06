"""Initial members harvest locally; a modest fixed tax funds infrastructure."""
# EVOLVE-BLOCK-START
def inventory_value(resources):
    resources = max(0.0, resources)
    return (
        0.20 * resources
        + 0.80 * min(0.85, resources)
        + 0.35 * min(1.70, max(0.0, resources - 0.85))
        + 0.12 * min(2.55, max(0.0, resources - 2.55))
    )
def stock_context(stock, capacity):
    ratio = stock / max(0.01, capacity)
    if ratio < 1.25:
        return 0
    if ratio < 3.0:
        return 1
    if ratio < 6.0:
        return 2
    return 3
def allocate_insurance(holdings, debts, budget):
    count = len(holdings)
    allocations = [0.0 for value in holdings]
    remaining = max(0.0, budget)
    priorities = []
    for index in range(count):
        gap = max(0.0, 0.90 - holdings[index])
        priorities.append((-4.0 * gap - debts[index], index))
    for priority, index in sorted(priorities):
        payment = min(
            remaining,
            max(0.0, 0.90 - holdings[index])
        )
        allocations[index] += payment
        remaining -= payment
    if count > 0 and remaining > 0.0:
        installment = remaining / 24.0
        for step in range(24):
            chosen = 0
            best_priority = -1.0
            for index in range(count):
                balance = holdings[index] + allocations[index]
                priority = (
                    (1.0 + 0.22 * debts[index])
                    / (0.60 + max(0.0, balance))
                )
                if priority > best_priority:
                    best_priority = priority
                    chosen = index
            allocations[chosen] += installment
    return allocations
def member_policy(observation, private_state):
    state = private_state or {}
    tick = observation['tick']
    society = observation['society_id']
    member = observation['member_id']
    societies = max(1, observation['n_societies'])
    members = max(1, observation['n_members'])
    wealth = max(0.0, observation['wealth'])
    capacity = 2.4 * observation['productivity']
    tax = min(0.8, max(0.0, observation['tax_rate']))
    patches = observation['patches']
    broadcast = observation.get('messages', {}) or {}
    fills = state.get('fills', {}).copy()
    raids = state.get('raids', {}).copy()
    previous = state.get('previous', {})
    transfer_base = state.get('transfer_base', 0.35 * tax * capacity)
    if previous:
        previous_action = previous.get('action')
        balance_receipt = (
            wealth - previous['wealth']
            + 0.85 + previous['cost']
        )
        if (
            previous_action == 'harvest'
            and wealth > 0.001
            and not previous.get('quoted_transfer', False)
            and previous['stock'] >= previous['capacity'] * (members + 3)
        ):
            direct_income = (
                previous['capacity'] * previous['effort']
                * (1.0 - previous['tax'])
            )
            observed_transfer = balance_receipt - direct_income
            if 0.0 <= observed_transfer <= 3.0:
                transfer_base = (
                    0.80 * transfer_base + 0.20 * observed_transfer
                )
        received = max(
            0.0,
            balance_receipt - previous.get('transfer', 0.0)
        )
        if wealth <= 0.001:
            received *= 0.5
        if previous_action == 'harvest':
            maximum = min(
                previous['stock'],
                previous['capacity'] * previous['effort']
            )
            if maximum > 0.001:
                gross = received / max(0.20, 1.0 - previous['tax'])
                fill = min(1.0, max(0.0, gross / maximum))
                key = previous['context']
                row = fills.get(key, [0.0, 0.0, tick])
                age = max(1, tick - row[2])
                discount = 1.0 / (1.0 + 0.08 * age)
                fills[key] = [
                    discount * row[0] + 1.0,
                    discount * row[1] + fill,
                    tick
                ]
        elif previous_action == 'raid':
            key = str(previous['target'])
            row = raids.get(key, [0.0, 0.0, 0.0, tick])
            age = max(1, tick - row[3])
            discount = 1.0 / (1.0 + 0.08 * age)
            loot = min(
                1.656,
                received / max(0.10, previous['effort'])
            )
            success = 1.0 if loot > 0.25 else 0.0
            raids[key] = [
                discount * row[0] + 1.0,
                discount * row[1] + success,
                discount * row[2] + success * loot,
                tick
            ]
    payments = {}
    if broadcast.get('protocol') == 'inventory_queues':
        payments = broadcast.get('payments', {})
    elif broadcast.get('protocol') == 'waterline_1':
        payments = broadcast.get('rebates', {})
    member_key = str(member)
    quoted_transfer = member_key in payments
    transfer = max(0.0, payments.get(member_key, transfer_base))
    raids_allowed = broadcast.get(
        'raid_permission',
        broadcast.get('raids', True)
    )
    baseline = inventory_value(wealth + transfer)
    action = 'rest'
    target = society
    effort = 0.0
    best_score = 0.0
    expected_income = 0.0
    chosen_stock = 0.0
    chosen_context = ''
    richest_patch = society
    richest_stock = 0.0
    for index, patch in enumerate(patches):
        stock = max(0.0, patch['stock'])
        patch_id = patch['id']
        if stock > richest_stock:
            richest_stock = stock
            richest_patch = patch_id
        if stock <= 0.0001:
            continue
        maximum = min(capacity, stock)
        harvest_effort = min(1.0, stock / max(0.01, capacity))
        context = str(patch_id) + ':' + str(stock_context(stock, capacity))
        row = fills.get(context, [0.0, 0.0, tick])
        age = max(0, tick - row[2])
        discount = 1.0 / (1.0 + 0.04 * age)
        samples = discount * row[0]
        successes = discount * row[1]
        prior = min(1.0, stock / max(0.01, 2.5 * maximum))
        probability = (2.0 * prior + successes) / (2.0 + samples)
        probability = min(1.0, max(0.0, probability))
        partial = 0.60 * min(probability, 1.0 - probability)
        full = probability - 0.5 * partial
        empty = 1.0 - probability - 0.5 * partial
        cost = min(wealth, 0.08 * harvest_effort)
        starting = max(0.0, wealth - cost) + transfer
        net_yield = maximum * (1.0 - tax)
        score = (
            empty * inventory_value(starting)
            + partial * inventory_value(starting + 0.5 * net_yield)
            + full * inventory_value(starting + net_yield)
            - baseline
        )
        score += 0.018 * net_yield / (1.0 + samples)
        score += 0.00003 * min(30.0, stock)
        score += 0.000001 * ((tick + member + index) % 3)
        if score > best_score:
            best_score = score
            action = 'harvest'
            target = patch_id
            effort = harvest_effort
            expected_income = probability * maximum
            chosen_stock = stock
            chosen_context = context
    if raids_allowed:
        for offset in range(1, societies):
            victim = (society + offset) % societies
            row = raids.get(str(victim), [0.0, 0.0, 0.0, tick])
            age = max(0, tick - row[3])
            discount = 1.0 / (1.0 + 0.05 * age)
            samples = discount * row[0]
            successes = discount * row[1]
            loot_sum = discount * row[2]
            probability = (2.1 + successes) / (3.0 + samples)
            loot = (2.1 * 1.45 + loot_sum) / (2.1 + successes)
            loot = min(1.656, max(0.0, loot))
            starting = max(0.0, wealth - min(wealth, 0.08)) + transfer
            score = (
                probability * inventory_value(starting + loot)
                + (1.0 - probability) * inventory_value(starting)
                - baseline
            )
            if wealth >= 1.70:
                score += 0.014 / (1.0 + samples)
            score += 0.000001 * ((tick + member + offset) % societies)
            if score > best_score:
                best_score = score
                action = 'raid'
                target = victim
                effort = 1.0
                expected_income = probability * loot
                chosen_stock = 0.0
                chosen_context = ''
    patch_report = []
    for patch in patches:
        patch_report.append([
            patch['id'],
            round(max(0.0, patch['stock']), 3)
        ])
    return {
        'action': action,
        'target': target,
        'effort': effort,
        'message': {
            'protocol': 'inventory_queues',
            'patches': patch_report,
            'patch': richest_patch,
            'stock': round(richest_stock, 3),
            'action': action,
            'target': target,
            'effort': round(effort, 4),
            'capacity': round(capacity, 4),
            'yield': round(expected_income, 4)
        },
        'state': {
            'fills': fills,
            'raids': raids,
            'transfer_base': transfer_base,
            'previous': {
                'action': action,
                'target': target,
                'wealth': wealth,
                'effort': effort,
                'capacity': capacity,
                'tax': tax,
                'stock': chosen_stock,
                'context': chosen_context,
                'cost': min(wealth, 0.08 * effort),
                'transfer': transfer,
                'quoted_transfer': quoted_transfer
            }
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
    wealths = [max(0.0, member['wealth']) for member in members]
    liquid = treasury + sum(wealths)
    reports = {}
    stocks = {}
    for report in observation.get('reports', []):
        message = report.get('message', {}) or {}
        reports[str(report['member'])] = message
        protocol = message.get('protocol')
        if protocol in ['inventory_queues', 'waterline_1']:
            for patch in message.get('patches', []):
                key = str(patch[0])
                stocks[key] = max(
                    stocks.get(key, 0.0),
                    max(0.0, patch[1])
                )
        elif 'patch' in message and 'stock' in message:
            key = str(message['patch'])
            stocks[key] = max(
                stocks.get(key, 0.0),
                max(0.0, message['stock'])
            )
    income = state.get('income', 2.2 * count)
    uncertainty = state.get('uncertainty', 0.30 * count)
    if 'liquid' in state:
        realized_investment = max(
            0.0,
            8.0 * count * (
                infrastructure - 0.96 * state.get('infrastructure', infrastructure)
            )
        )
        measured_income = (
            liquid - state['liquid']
            + 0.93 * count + realized_investment
        )
        measured_income = min(3.2 * count, max(0.0, measured_income))
        uncertainty = (
            0.75 * uncertainty
            + 0.25 * abs(measured_income - income)
        )
        adjustment = 0.50 if measured_income < 0.75 * income else 0.25
        income = (1.0 - adjustment) * income + adjustment * measured_income
    pressure = state.get('pressure', 0.0)
    if stocks:
        ordered_stocks = sorted(stocks.values())
        median_stock = ordered_stocks[len(ordered_stocks) // 2]
        observed_pressure = min(
            1.0,
            max(0.0, (7.2 - median_stock) / 7.2)
        )
        pressure = 0.45 * pressure + 0.55 * observed_pressure
    supply_queue = min(
        6.0 * count,
        0.80 * state.get('supply_queue', 0.0)
        + max(0.0, 0.93 * count - income)
    )
    old_debts = state.get('debts', {})
    debt_map = {}
    debts = []
    for index, member in enumerate(members):
        key = str(member['id'])
        debt = min(
            6.0,
            0.88 * old_debts.get(key, 0.0)
            + max(0.0, 1.10 - wealths[index])
        )
        debt_map[key] = debt
        debts.append(debt)
    cautious_income = max(0.0, income - 0.35 * uncertainty)
    fallback = min(2.4, max(0.15, cautious_income / count))
    harvests = []
    other_income = []
    contributions = 0.0
    for index, member in enumerate(members):
        message = reports.get(str(member['id']), {})
        reported_action = message.get('action', 'harvest')
        reported_effort = min(1.0, max(0.0, message.get('effort', 1.0)))
        cost = min(wealths[index], 0.08 * reported_effort)
        harvest = 0.0
        other = -cost
        if reported_action == 'harvest':
            capacity = min(2.76, max(0.1, message.get('capacity', 2.4)))
            estimate = fallback
            if message.get('protocol') == 'inventory_queues':
                estimate = max(0.0, message.get('yield', fallback))
            else:
                patch_key = str(message.get('target', message.get('patch')))
                if patch_key in stocks:
                    estimate = min(
                        capacity * reported_effort,
                        stocks[patch_key] / 2.5
                    )
            harvest = min(
                capacity * reported_effort,
                max(0.0, 0.60 * fallback + 0.40 * estimate)
            )
        elif reported_action == 'raid':
            estimate = 0.80
            if message.get('protocol') == 'inventory_queues':
                estimate = message.get('yield', estimate)
            other += min(1.656, max(0.0, estimate))
        elif reported_action == 'contribute':
            contribution = min(
                max(0.0, wealths[index] - cost),
                2.0 * reported_effort
            )
            contributions += contribution
            other -= contribution
        elif reported_action == 'share':
            other -= min(
                max(0.0, wealths[index] - cost),
                2.0 * reported_effort
            )
        elif reported_action == 'rest':
            other = 0.0
        harvests.append(harvest)
        other_income.append(other)
    surplus = max(
        0.0,
        liquid - count * (2.10 + 0.80 * pressure)
    )
    infrastructure_target = (
        0.70 + 0.70 * pressure
        + min(0.90, supply_queue / (2.0 * count))
    )
    construction_request = max(
        0.0,
        8.0 * count * (
            0.04 * infrastructure
            + 0.12 * (infrastructure_target - infrastructure)
        )
    )
    planned_investment = min(
        construction_request,
        0.13 * surplus,
        max(0.0, 0.55 * (cautious_income - 0.93 * count) + 0.035 * surplus)
    )
    reserve_goal = min(
        0.85 * count,
        0.15 * max(0.0, liquid - 0.93 * count)
    )
    total_harvest = sum(harvests)
    tax = 0.0
    best_loss = 1000000000.0
    for candidate_tax in [0.0, 0.08, 0.16, 0.24, 0.32, 0.40, 0.48]:
        candidate_pool = treasury + contributions + candidate_tax * total_harvest
        essential_gap = 0.0
        buffer_gap = 0.0
        for index in range(count):
            holding = max(
                0.0,
                wealths[index]
                + (1.0 - candidate_tax) * harvests[index]
                + other_income[index]
            )
            essential_gap += max(0.0, 0.90 - holding)
            buffer_gap += max(
                0.0,
                1.70 + 0.12 * debts[index] - holding
            )
        funding_gap = max(
            0.0,
            buffer_gap + planned_investment + reserve_goal - candidate_pool
        )
        loss = (
            6.0 * max(0.0, essential_gap - candidate_pool)
            + 1.5 * funding_gap
            + 0.06 * candidate_tax * total_harvest
            + 0.03 * candidate_tax
        )
        if loss < best_loss:
            best_loss = loss
            tax = candidate_tax
    holdings = []
    buffer_gap = 0.0
    for index in range(count):
        holding = max(
            0.0,
            wealths[index]
            + (1.0 - tax) * harvests[index]
            + other_income[index]
        )
        holdings.append(holding)
        buffer_gap += max(0.0, 1.70 + 0.12 * debts[index] - holding)
    pool = max(0.0, treasury + contributions + tax * total_harvest)
    investment = min(
        planned_investment,
        0.50 * pool,
        max(0.0, pool - buffer_gap)
    )
    reserve = min(
        reserve_goal,
        max(0.0, pool - buffer_gap - investment)
    )
    distribution_budget = max(0.0, pool - investment - reserve)
    allocations = allocate_insurance(holdings, debts, distribution_budget)
    weights = allocations
    if sum(weights) <= 0.000001:
        weights = []
        for index in range(count):
            weights.append(
                (1.0 + 0.22 * debts[index]) / (0.60 + holdings[index])
            )
    weight_total = sum(weights)
    payments = {}
    for index, member in enumerate(members):
        payments[str(member['id'])] = round(
            distribution_budget * weights[index] / weight_total,
            4
        )
    public_fraction = 0.0
    reserve_fraction = 0.0
    if pool > 0.000001:
        public_fraction = investment / pool
        reserve_fraction = reserve / pool
    return {
        'tax_rate': tax,
        'public_fraction': public_fraction,
        'defense_fraction': 0.0,
        'reserve_fraction': reserve_fraction,
        'redistribution': weights,
        'raid_permission': True,
        'messages': {
            'protocol': 'inventory_queues',
            'payments': payments,
            'raids': True
        },
        'state': {
            'liquid': liquid,
            'infrastructure': infrastructure,
            'income': income,
            'uncertainty': uncertainty,
            'pressure': pressure,
            'supply_queue': supply_queue,
            'debts': debt_map
        }
    }
# EVOLVE-BLOCK-END
