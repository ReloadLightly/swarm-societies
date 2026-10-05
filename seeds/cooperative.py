"""Fixed, credible risk-sharing institution and adaptive harvesting members."""
# EVOLVE-BLOCK-START

def member_policy(observation, private_state):
    estimates = private_state.get('stocks', {})
    previous = estimates.copy()
    for patch in observation['patches']:
        estimates[str(patch['id'])] = patch['stock']
    for report in observation['messages'].get('reports', []):
        msg = report.get('message', {})
        if 'patch' in msg and 'stock' in msg:
            estimates[str(msg['patch'])] = msg['stock']
    visible = observation['patches']
    best = max(visible, key=lambda p: p['stock'] + 0.1 * (p['stock'] - previous.get(str(p['id']), p['stock'])))
    action = 'harvest'
    if observation['wealth'] > 7 and observation['infrastructure'] < 2.2 and not observation['messages'].get('shortage', False):
        action = 'contribute'
    if observation['wealth'] > 11 and observation['tick'] % 5 == observation['member_id'] % 5:
        action = 'share'
    target = (observation['society_id'] + 1) % observation['n_societies'] if action == 'share' else best['id']
    return {'action': action, 'target': target, 'effort': 1.0,
            'message': {'patch': best['id'], 'stock': best['stock']},
            'state': {'stocks': estimates}}


def institution(observation, shared_state):
    average = observation['mean_wealth']
    shortage = average < 2.0
    weights = [max(0.2, 5 - member['wealth']) for member in observation['members']]
    return {'tax_rate': 0.28, 'public_fraction': 0.15 if shortage else 0.5,
            'defense_fraction': 0.15, 'reserve_fraction': 0.05,
            'raid_permission': False, 'redistribution': weights,
            'messages': {'reports': observation['reports'], 'shortage': shortage},
            'state': {'wealth_history': (shared_state.get('wealth_history', []) + [average])[-8:]}}
# EVOLVE-BLOCK-END
