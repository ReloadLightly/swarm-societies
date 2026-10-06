"""Reconstructed external-review baseline; original reviewer source not supplied."""
def member_policy(observation, private_state):
    patch = max(observation['patches'], key=lambda p: p['stock'])
    return {'action': 'harvest', 'target': patch['id'], 'effort': 1.0,
            'message': {}, 'state': {}}

def institution(observation, shared_state):
    return {'tax_rate': 0.0, 'public_fraction': 0.0, 'defense_fraction': 0.0,
            'reserve_fraction': 0.0, 'raid_permission': False,
            'redistribution': [1.0 for member in observation['members']],
            'messages': {}, 'state': {}}
