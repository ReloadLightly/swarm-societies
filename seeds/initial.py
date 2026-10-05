"""Initial members harvest locally; a modest fixed tax funds infrastructure."""
# EVOLVE-BLOCK-START

def member_policy(observation, private_state):
    seen = private_state.get('seen', 0) + 1
    local = observation['patches']
    chosen = max(local, key=lambda p: p['stock'])['id']
    action = 'contribute' if observation['wealth'] > 9 and observation['member_id'] % 3 == 0 else 'harvest'
    return {'action': action, 'target': chosen, 'effort': 1.0,
            'message': {'patch': chosen, 'stock': max(p['stock'] for p in local)},
            'state': {'seen': seen}}


def institution(observation, shared_state):
    return {'tax_rate': 0.15, 'public_fraction': 0.45, 'defense_fraction': 0.10,
            'reserve_fraction': 0.10, 'raid_permission': True,
            'redistribution': [1 for x in observation['members']],
            'messages': {'reports': observation['reports']},
            'state': {'ticks': shared_state.get('ticks', 0) + 1}}
# EVOLVE-BLOCK-END
