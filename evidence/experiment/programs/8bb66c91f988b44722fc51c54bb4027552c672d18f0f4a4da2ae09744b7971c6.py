"""Extractive partner/opponent snapshot, with no sharing institution."""
# EVOLVE-BLOCK-START

def member_policy(observation, private_state):
    action = 'raid' if observation['tick'] % 3 == observation['member_id'] % 3 else 'harvest'
    target = (observation['society_id'] + 1) % observation['n_societies'] if action == 'raid' else max(observation['patches'], key=lambda p: p['stock'])['id']
    return {'action': action, 'target': target, 'effort': 1.0,
            'state': {'actions': private_state.get('actions', 0) + 1}}


def institution(observation, shared_state):
    return {'tax_rate': 0, 'public_fraction': 0, 'defense_fraction': 0,
            'reserve_fraction': 0, 'raid_permission': True,
            'redistribution': [1 for x in observation['members']], 'messages': {}, 'state': {}}
# EVOLVE-BLOCK-END
