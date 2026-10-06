ROLE_ROTATION = 2

def institution(obs, state):
    role = (obs['society_id'] + ROLE_ROTATION) % 3
    phase = (obs['tick'] // 8 + role * 3) % 9
    public = 0.0 if phase < 3 else (0.3 if phase < 6 else 0.8)
    return {'tax_rate': 0.6, 'public_fraction': public,
            'defense_fraction': 0.0, 'reserve_fraction': 0.0,
            'raid_permission': False, 'state': {}}

def member_policy(obs, state):
    home = obs['society_id']
    target = home
    if (obs['tick'] + obs['member_id']) % 5 == 0:
        for patch in obs['patches']:
            if patch['id'] != home:
                target = patch['id']
    return {'action': 'harvest', 'target': target, 'effort': 1.0, 'state': {}}
