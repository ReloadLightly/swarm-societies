"""Initial members harvest locally; a modest fixed tax funds infrastructure."""
# EVOLVE-BLOCK-START
def cash_value(balance, remaining):
    balance = max(0.0, balance)
    surplus = max(0.0, balance - 0.85)
    return (
        min(0.85, balance)
        + 0.2 * surplus
        + 0.10 * min(1.0, remaining / 8.0) * min(3.0, surplus)
    )
def member_policy(observation, private_state):
    memory = private_state or {}
    tick = observation['tick']
    society = observation['society_id']
    member = observation['member_id']
    wealth = max(0.0, observation['wealth'])
    capacity = 2.4 * observation['productivity']
    tax = observation['tax_rate']
    messages = observation.get('messages', {})
    remaining = max(1, 60 - tick)
    beliefs = memory.get('beliefs', {}).copy()
    visits = memory.get('visits', {}).copy()
    raids = memory.get('raids', {}).copy()
    offsets = list(memory.get('offsets', []))
    prior = [0.15, 0.22, 0.23, 0.18, 0.10, 0.12]
    ordered = sorted(offsets)
    offset = ordered[len(ordered) // 2] if ordered else 0.0
    if memory.get('tick', -2) == tick - 1:
        transfer = messages.get('previous_transfers', {}).get(
            str(member), 0.0
        )
        receipt = (
            wealth - memory.get('wealth', wealth)
            + 0.85 + 0.08 * memory.get('effort', 0.0)
            - transfer
        )
        previous_action = memory.get('action', 'rest')
        previous_key = str(memory.get('target', society))
        if previous_action == 'harvest' and wealth > 0.02:
            predictions = memory.get('predictions', [])
            retention = 1.0 - memory.get('tax', tax)
            if predictions:
                if max(predictions) - min(predictions) < 0.03:
                    residual = receipt - retention * max(predictions)
                    offsets.append(max(-1.4, min(0.8, residual)))
                    offsets = offsets[-7:]
                    ordered = sorted(offsets)
                    offset = ordered[len(ordered) // 2]
                signal = receipt - offset
                upper = retention * max(predictions)
                if signal >= -0.15 and signal <= upper + 0.6:
                    probabilities = beliefs.get(previous_key, prior)
                    updated = []
                    for index, prediction in enumerate(predictions):
                        error = signal - retention * prediction
                        likelihood = 1.0 / (0.20 + error * error)
                        updated.append(
                            (0.94 * probabilities[index] + 0.01)
                            * likelihood
                        )
                    total = max(0.0001, sum(updated))
                    beliefs[previous_key] = [
                        0.94 * value / total + 0.01
                        for value in updated
                    ]
        elif previous_action == 'raid':
            record = raids.get(
                previous_key, [3.0, 1.0, 1.656, 1.0, tick - 1]
            )
            signal = max(0.0, min(1.656, receipt - offset))
            if wealth <= 0.02:
                signal = 0.0
            success = 1.0 if signal > 0.25 else 0.0
            successes = 0.94 * record[0] + success
            failures = 0.94 * record[1] + 1.0 - success
            prize = record[2]
            samples = record[3]
            if success > 0.0:
                prize = (prize * samples + signal) / (samples + 1.0)
                samples = min(12.0, samples + 1.0)
            raids[previous_key] = [
                successes, failures, prize, samples, tick
            ]
    action = 'rest'
    target = society
    effort = 0.0
    best_score = cash_value(wealth, remaining)
    selected_predictions = []
    visible = []
    best_patch = society
    best_stock = 0.0
    best_harvest_score = -1.0
    for index, patch in enumerate(observation['patches']):
        stock = max(0.0, patch['stock'])
        patch_id = patch['id']
        key = str(patch_id)
        visible.append({'id': patch_id, 'stock': stock})
        harvest_effort = min(1.0, stock / max(0.01, capacity))
        limit = capacity * harvest_effort
        predictions = [
            min(limit, stock),
            min(limit, stock / 2.0),
            min(limit, stock / 3.0),
            min(limit, stock / 4.5),
            min(limit, stock / 6.0),
            min(
                limit,
                max(0.0, stock - 2.4 * observation['n_members'])
            )
        ]
        probabilities = beliefs.get(key, prior)
        score = 0.0
        for probability, predicted in zip(probabilities, predictions):
            balance = (
                wealth + predicted * (1.0 - tax)
                - min(wealth, 0.08 * harvest_effort)
            )
            score += probability * cash_value(balance, remaining)
        if stock > 0.0:
            score += 0.001 * stock / (1.0 + stock)
            score += (
                0.0005
                * ((7 * member + 3 * tick + 11 * index) % 17)
                / 17.0
            )
            if wealth > 3.0 and remaining > 6:
                score += 0.006 / (1.0 + visits.get(key, 0))
        if score > best_harvest_score:
            best_harvest_score = score
            best_patch = patch_id
            best_stock = stock
        if stock > 0.0 and score > best_score:
            best_score = score
            action = 'harvest'
            target = patch_id
            effort = harvest_effort
            selected_predictions = predictions
    if messages.get('raid_permission', True):
        societies = observation['n_societies']
        for step in range(societies):
            other = (member + tick + step) % societies
            if other == society:
                continue
            key = str(other)
            record = raids.get(key, [3.0, 1.0, 1.656, 1.0, tick])
            age = max(0, tick - record[4])
            trust = 12.0 / (12.0 + age)
            learned_probability = record[0] / max(
                0.01, record[0] + record[1]
            )
            probability = (
                trust * learned_probability + (1.0 - trust) * 0.65
            )
            prize = trust * record[2] + (1.0 - trust) * 1.4
            cost = min(wealth, 0.08)
            score = (
                probability
                * cash_value(wealth + prize - cost, remaining)
                + (1.0 - probability)
                * cash_value(wealth - cost, remaining)
            )
            if wealth > 3.0 and remaining > 8:
                score += 0.025 / (1.0 + record[0] + record[1])
            if score > best_score + 0.025:
                best_score = score
                action = 'raid'
                target = other
                effort = 1.0
                selected_predictions = []
    if action == 'harvest':
        key = str(target)
        visits[key] = min(100, visits.get(key, 0) + 1)
    return {
        'action': action,
        'target': target,
        'effort': effort,
        'message': {
            'patch': best_patch,
            'stock': best_stock,
            'patches': visible,
            'action': action,
            'target': target,
            'effort': effort,
            'productivity': observation['productivity'],
            'wealth': wealth
        },
        'state': {
            'tick': tick,
            'wealth': wealth,
            'tax': tax,
            'action': action,
            'target': target,
            'effort': effort,
            'predictions': selected_predictions,
            'beliefs': beliefs,
            'visits': visits,
            'raids': raids,
            'offsets': offsets
        }
    }
def insurance_split(holdings, budget, buffer):
    grants = [0.0 for value in holdings]
    order = sorted([
        [value, index] for index, value in enumerate(holdings)
    ])
    left = max(0.0, budget)
    for value, index in order:
        grant = min(left, max(0.0, 0.98 - value))
        grants[index] = grant
        left -= grant
    pressure = [
        max(0.0, buffer - value - grants[index])
        for index, value in enumerate(holdings)
    ]
    weights = [0.02 + value * value for value in pressure]
    total = max(0.01, sum(weights))
    for index in range(len(grants)):
        grants[index] += left * weights[index] / total
    return grants
def fiscal_trial(model, tax, public, defense):
    count = model['count']
    gross = model['gross']
    income = model['income']
    capacities = model['capacity']
    total_gross = sum(gross)
    old_tax = model['previous_tax']
    initial_infrastructure = model['infrastructure']
    tax_flow = total_gross * (tax - old_tax)
    first_grants = []
    first_pool = 0.0
    combined_score = 0.0
    for scenario in range(2):
        wealth = list(model['wealth'])
        infrastructure = initial_infrastructure
        score = 0.0
        probability = (
            model['stress_weight']
            if scenario == 1
            else 1.0 - model['stress_weight']
        )
        for step in range(model['horizon']):
            harvests = []
            earnings = []
            growth = 1.1 * (
                infrastructure - initial_infrastructure
            ) / count
            for index in range(len(wealth)):
                harvest = gross[index]
                if harvest > 0.01:
                    harvest = min(
                        capacities[index], max(0.0, harvest + growth)
                    )
                    if scenario == 1:
                        harvest *= 0.80 - 0.08 * model['shock']
                earned = (
                    income[index]
                    + gross[index] * (old_tax - tax)
                    + (harvest - gross[index]) * (1.0 - tax)
                )
                if scenario == 1:
                    earned -= 0.12 + 0.40 * model['risk'][index]
                harvests.append(harvest)
                earnings.append(earned)
            pool = max(
                0.0,
                model['flow'] + tax_flow
                + tax * (sum(harvests) - total_gross)
            )
            if step == 0:
                pool += model['treasury']
            holdings = [
                max(0.0, value + earnings[index])
                for index, value in enumerate(wealth)
            ]
            grants = insurance_split(
                holdings,
                pool * max(0.0, 1.0 - public - defense),
                model['buffer']
            )
            if scenario == 0 and step == 0:
                first_grants = grants
                first_pool = pool
            shortfall = 0.0
            fragility = 0.0
            for index in range(len(wealth)):
                available = holdings[index] + grants[index]
                shortfall += max(0.0, 0.85 - available)
                wealth[index] = max(0.0, available - 0.85)
                fragility += max(
                    0.0, min(1.5, model['buffer']) - wealth[index]
                )
            infrastructure = (
                0.96 * infrastructure + public * pool / (8.0 * count)
            )
            score += (
                0.03 * infrastructure
                - 1.6 * shortfall / count
                - 0.006 * fragility
            )
        score += model['terminal_capital'] * infrastructure
        score += model['terminal_cash'] * sum(
            min(model['buffer'], value) for value in wealth
        )
        combined_score += probability * score
    return [combined_score, first_grants, first_pool]
def institution(observation, shared_state):
    memory = shared_state or {}
    members = observation['members']
    count = max(1, len(members))
    tick = observation['tick']
    remaining = max(1, 60 - tick)
    treasury = max(0.0, observation['treasury'])
    infrastructure = max(0.0, observation['infrastructure'])
    previous_tax = memory.get('tax', 0.35)
    previous_people = memory.get('people', {})
    reports = {}
    stocks = []
    for report in observation.get('reports', []):
        message = report.get('message', {})
        reports[str(report['member'])] = message
        if 'stock' in message:
            stocks.append(max(0.0, message['stock']))
    stock_level = (
        sum(stocks) / len(stocks)
        if stocks else memory.get('stock_level', 16.0)
    )
    anchor = memory.get('stock_anchor', stock_level)
    shock = max(
        0.0, min(1.0, (anchor - stock_level) / max(1.0, anchor))
    )
    anchor = 0.92 * anchor + 0.08 * stock_level
    previous_pool = memory.get('pool', 0.0)
    measured = False
    previous_public = memory.get('public', 0.0)
    if previous_people and previous_public > 0.025:
        investment = 8.0 * count * (
            infrastructure - 0.96 * memory.get(
                'infrastructure', infrastructure
            )
        )
        if investment >= 0.0:
            previous_pool = min(
                8.0 * count, investment / previous_public
            )
            measured = True
    previous_distribution = previous_pool * max(
        0.0,
        1.0 - previous_public - memory.get('defense', 0.0)
    )
    previous_transfers = {}
    wealths = []
    incomes = []
    harvests = []
    capacities = []
    risks = []
    for member in members:
        key = str(member['id'])
        wealth = max(0.0, member['wealth'])
        previous = previous_people.get(key, {})
        report = reports.get(key, {})
        capacity = 2.4 * report.get(
            'productivity', previous.get('productivity', 1.0)
        )
        stock = max(0.0, report.get('stock', stock_level))
        proxy = min(capacity, stock / 2.6)
        gross = (
            0.6 * previous.get('gross', 0.92 * capacity)
            + 0.4 * proxy
        )
        reported_action = report.get('action', 'harvest')
        default_income = gross * (1.0 - previous_tax) - 0.08
        if reported_action == 'contribute' or reported_action == 'share':
            gross = 0.0
            default_income = -2.08 * report.get('effort', 1.0)
        elif reported_action == 'rest':
            gross = 0.0
            default_income = 0.0
        elif reported_action == 'guard':
            gross = 0.0
            default_income = -0.08 * report.get('effort', 1.0)
        elif reported_action == 'raid':
            gross = 0.0
            default_income = 0.8
        transfer = (
            previous_distribution * previous.get('share', 0.0)
        )
        previous_transfers[key] = transfer
        income = previous.get('income', default_income)
        risk = previous.get('risk', 0.15)
        if previous:
            observed = wealth - previous['wealth'] + 0.85 - transfer
            observed = max(-3.0, min(3.0, observed))
            if wealth <= 0.02:
                observed = min(observed, 0.35)
            surprise = max(0.0, income - observed - 0.25)
            risk = 0.75 * risk + 0.25 * min(2.5, surprise)
            income = 0.4 * income + 0.6 * observed
            if reported_action == 'harvest' and observed > 0.1:
                inferred = min(
                    capacity,
                    max(0.0, observed + 0.08 + 0.4 * risk)
                    / max(0.2, 1.0 - previous_tax)
                )
                gross = 0.75 * gross + 0.25 * inferred
        else:
            income = default_income
        wealths.append(wealth)
        incomes.append(income)
        harvests.append(gross)
        capacities.append(capacity)
        risks.append(risk)
    flow = memory.get('flow', sum(harvests) * previous_tax)
    if measured:
        observed_flow = max(
            0.0, previous_pool - memory.get('treasury', 0.0)
        )
        flow = 0.35 * flow + 0.65 * observed_flow
    horizon = min(4, remaining)
    terminal_capital = 0.0
    decay = 0.96
    for step in range(max(0, remaining - horizon)):
        terminal_capital += 0.03 * decay
        decay *= 0.96
    buffer = min(2.5 + shock, 0.85 * remaining)
    defense = min(
        0.12,
        0.22 * sum(risks) / max(0.5, treasury + flow)
    )
    model = {
        'count': count,
        'wealth': wealths,
        'income': incomes,
        'gross': harvests,
        'capacity': capacities,
        'risk': risks,
        'previous_tax': previous_tax,
        'infrastructure': infrastructure,
        'treasury': treasury,
        'flow': flow,
        'horizon': horizon,
        'buffer': buffer,
        'shock': shock,
        'stress_weight': 0.22 + 0.30 * shock,
        'terminal_capital': terminal_capital,
        'terminal_cash': 0.018 * min(1.0, remaining / 8.0)
    }
    best_score = -1000000.0
    best_tax = 0.54
    best_public = 0.5
    best_grants = [1.0 for member in members]
    best_pool = max(0.0, treasury + flow)
    for tax in [0.30, 0.54, 0.78]:
        pool = max(
            0.1, treasury + flow + sum(harvests) * (tax - previous_tax)
        )
        support = sum(
            max(
                0.0,
                0.85 - incomes[index]
                - harvests[index] * (previous_tax - tax)
                + (buffer - wealths[index]) / max(1, horizon)
            )
            for index in range(len(members))
        )
        center = max(
            0.04, min(1.0 - defense, 1.0 - defense - support / pool)
        )
        candidates = []
        for change in [-0.24, 0.0, 0.24]:
            public = max(
                0.04, min(1.0 - defense, center + change)
            )
            if public not in candidates:
                candidates.append(public)
        for public in candidates:
            result = fiscal_trial(model, tax, public, defense)
            score = result[0]
            score -= 0.001 * abs(tax - previous_tax)
            if score > best_score:
                best_score = score
                best_tax = tax
                best_public = public
                best_grants = result[1]
                best_pool = result[2]
    weights = best_grants
    total_weight = sum(weights)
    if total_weight <= 0.00001:
        weights = [1.0 for member in members]
        total_weight = max(1.0, sum(weights))
    people = {}
    for index, member in enumerate(members):
        people[str(member['id'])] = {
            'wealth': wealths[index],
            'income': (
                incomes[index]
                + harvests[index] * (previous_tax - best_tax)
            ),
            'gross': harvests[index],
            'productivity': capacities[index] / 2.4,
            'risk': risks[index],
            'share': weights[index] / total_weight
        }
    return {
        'tax_rate': best_tax,
        'public_fraction': best_public,
        'defense_fraction': defense,
        'reserve_fraction': 0.0,
        'redistribution': weights,
        'raid_permission': False,
        'messages': {
            'raid_permission': False,
            'previous_transfers': previous_transfers,
            'buffer': buffer,
            'scarcity': shock > 0.3,
            'resource_trend': stock_level - memory.get(
                'stock_level', stock_level
            )
        },
        'state': {
            'tick': tick,
            'tax': best_tax,
            'public': best_public,
            'defense': defense,
            'people': people,
            'pool': best_pool,
            'treasury': treasury,
            'infrastructure': infrastructure,
            'flow': max(
                0.0, flow + sum(harvests) * (best_tax - previous_tax)
            ),
            'stock_level': stock_level,
            'stock_anchor': anchor
        }
    }
# EVOLVE-BLOCK-END
