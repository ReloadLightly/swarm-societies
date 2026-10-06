"""Frozen sharing designs, information boundaries and semantic evidence checks."""

import json
import shutil

import pytest

from scripts import run_world_model_sharing as sharing
from swarm_societies.world_model_v1.learner import RenewalSMC
from swarm_societies.world_model_v1.sharing import actor_seed


@pytest.fixture(scope='module')
def tiny_sharing(tmp_path_factory):
    directory = tmp_path_factory.mktemp('sharing-study-control')
    design = sharing.prepare(directory,arenas=2,ticks=8,development=True)
    # Reduced numerical work is a test-only design in the development namespace.
    design['learner_settings'] = {'n_particles':32,'rejuvenation_steps':1,'ess_fraction':.5}
    design['n_probes'],design['forecast_samples'] = 4,32
    sharing.json_write(directory/'design.json',design)
    (directory/'design.sha256').write_text(sharing.sha(directory/'design.json')+'\n')
    outcomes = [sharing.run_case((directory,case,design)) for case in design['cases']]
    tables = {}
    for name in ('checkpoints','parameters','transport','costs'):
        tables[name] = [row for case in design['cases'] for row in
            sharing.csv_read(directory/'cases'/case['arena_id']/(name+'.csv'))]
        sharing.csv_write(directory/(name+'.csv'),tables[name])
    summary = sharing.summarize(tables['checkpoints'],tables['transport'],tables['costs'],design)
    sharing.json_write(directory/'summary.json',summary)
    files = sorted(path for path in directory.rglob('*') if path.is_file())
    sharing.json_write(directory/'completion.json',{'study':sharing.VERSION,'model_generation_calls':0,
        'outcomes':outcomes,'artifacts':{str(path.relative_to(directory)):sharing.sha(path) for path in files}})
    return directory,design,tables,summary


def copy_study(tiny_sharing,tmp_path):
    destination = tmp_path/'evidence'
    shutil.copytree(tiny_sharing[0],destination)
    return destination


def rehash(directory,relative):
    manifest = json.loads((directory/'completion.json').read_text())
    manifest['artifacts'][relative] = sharing.sha(directory/relative)
    sharing.json_write(directory/'completion.json',manifest)


def test_small_study_semantically_verifies_all_grid_and_terminal_forecasts(tiny_sharing):
    result = sharing.verify(tiny_sharing[0])
    assert result['verified']
    assert result['arenas'] == 2
    assert result['checkpoints'] == 810
    assert result['parameter_rows'] == 2430
    assert result['prediction_rows'] == 3240
    assert result['terminal_forecasts_regenerated'] == 600


def test_sensor_stream_is_canonical_legal_and_separate_from_probes(tiny_sharing):
    _,design,_,_ = tiny_sharing
    case = design['cases'][0]
    packets,probes,audit = sharing.generate_case(case,design)
    assert (packets,probes,audit) == sharing.generate_case(case,design)
    assert len(packets) == 24 and len({row['event_id'] for row in packets}) == 24
    allowed = {'event_id','tick','patch','phase','stock_before','capacity','own_infrastructure',
               'other_infrastructure','growth','sensor_sigma'}
    assert all(set(packet) == allowed for packet in packets)
    assert all(packet['event_id'].startswith(case['arena_id']+'/') for packet in packets)
    assert {packet['tick'] for packet in packets} == set(range(8))
    assert abs(audit['ledger_residual']) < 1e-7
    assert [probe['probe_group'] for probe in probes] == ['uncapped','capacity_control']*2


def test_fresh_case_banks_do_not_reuse_prior_experimental_worlds(tiny_sharing,tmp_path):
    evaluation = sharing.prepare(tmp_path/'evaluation',arenas=2,ticks=8)
    assert not {case['arena_id'] for case in evaluation['cases']} & {
        case['arena_id'] for case in tiny_sharing[1]['cases']}
    assert not {case['environment_seed'] for case in evaluation['cases']} & {
        case['environment_seed'] for case in tiny_sharing[1]['cases']}


def test_content_contrast_matches_bytes_and_delay_retains_pending_work(tiny_sharing):
    _,design,tables,_ = tiny_sharing
    for case in design['cases']:
        arena = case['arena_id']
        totals = {condition:sum(int(row['sent_bytes']) for row in tables['transport']
            if row['arena_id'] == arena and row['condition'] == condition) for condition in sharing.CONDITIONS}
        assert totals['redundant'] == totals['complementary'] == 3*(2*8+8*7)*1024
        assert totals['delayed_complementary'] == 3*(2*8+8*4)*1024
        assert totals['isolated'] == totals['union_ceiling'] == 0
        for row in tables['transport']:
            if row['arena_id'] == arena and row['condition'] == 'delayed_complementary':
                assert int(row['novel_member_updates']) == 0
                assert int(row['pending_frames']) > 0


def test_exact_evidence_checkpoints_respect_start_tick_availability(tiny_sharing):
    rows = tiny_sharing[2]['checkpoints']
    selected = {row['condition']:row for row in rows if row['arena_id'] == tiny_sharing[1]['cases'][0]['arena_id']
        and row['actor'] == 'member:0:0' and row['axis'] == 'evidence' and int(row['coordinate']) == 8}
    assert all(int(row['unique_observations']) == 8 for row in selected.values())
    assert int(selected['complementary']['completed_ticks']) == 3
    assert int(selected['isolated']['completed_ticks']) == 4
    assert int(selected['redundant']['completed_ticks']) == 4
    assert int(selected['union_ceiling']['completed_ticks']) == 3


def test_direct_event_stream_replay_recovers_all_private_and_institutional_models(tiny_sharing):
    directory,design,_,_ = tiny_sharing
    case = design['cases'][0]
    snapshot = sharing.packed_read(directory/'cases'/case['arena_id']/'complementary.json.gz')
    assert len(snapshot['models']) == 15
    for actor,expected in snapshot['models'].items():
        replay = RenewalSMC(seed=actor_seed(snapshot['seed'],actor),**snapshot['learner_kwargs'])
        events = [row for row in snapshot['updates'] if row['actor_key'] == actor]
        for event in events:
            assert replay.update(snapshot['store'][event['event_id']])['status'] == event['status']
        assert replay.snapshot() == expected


def test_unreached_evidence_checkpoint_prevents_complete_panel_summary(tiny_sharing):
    _,design,tables,_ = tiny_sharing
    records = [row for row in tables['checkpoints'] if not (
        row['actor'] == 'member:0:0' and row['condition'] == 'isolated'
        and row['axis'] == 'evidence' and int(row['coordinate']) == 16)]
    with pytest.raises(ValueError,match='Incomplete exact-evidence checkpoint coverage'):
        sharing.summarize(records,tables['transport'],tables['costs'],design)


def test_design_checksum_detects_changed_conditions(tiny_sharing,tmp_path):
    directory = copy_study(tiny_sharing,tmp_path)
    design = json.loads((directory/'design.json').read_text())
    design['frame_bytes'] = 2048
    sharing.json_write(directory/'design.json',design)
    with pytest.raises(ValueError,match='design checksum'):
        sharing.verify(directory)


@pytest.mark.parametrize('field,value,message',[
    ('growth',999.,'Regenerated arena data'),
    ('event_id','foreign/growth:0:0','Regenerated arena data'),
])
def test_tampered_sensor_primitives_fail_after_checksum_rewrite(tiny_sharing,tmp_path,field,value,message):
    directory = copy_study(tiny_sharing,tmp_path)
    relative = f'cases/{tiny_sharing[1]["cases"][0]["arena_id"]}/data.json.gz'
    data = sharing.packed_read(directory/relative)
    data['packets'][0][field] = value
    sharing.packed_write(directory/relative,data)
    rehash(directory,relative)
    with pytest.raises(ValueError,match=message):
        sharing.verify(directory)


@pytest.mark.parametrize('mutation,match',[
    ('frame_bytes','Transport reconstruction differs: frames'),
    ('delivery','Transport reconstruction differs: frames'),
    ('ownership','Transport reconstruction differs: owners'),
    ('update','Transport reconstruction differs: updates'),
    ('likelihood','Posterior cached likelihood'),
])
def test_transport_and_posterior_tampering_fails_after_checksum_rewrite(tiny_sharing,tmp_path,mutation,match):
    directory = copy_study(tiny_sharing,tmp_path)
    relative = f'cases/{tiny_sharing[1]["cases"][0]["arena_id"]}/complementary.json.gz'
    snapshot = sharing.packed_read(directory/relative)
    if mutation == 'frame_bytes':
        snapshot['frames'][0]['bytes'] = 1
    elif mutation == 'delivery':
        snapshot['frames'][0]['delivery_tick'] += 1
    elif mutation == 'ownership':
        snapshot['owners'][next(iter(snapshot['owners']))] = []
    elif mutation == 'update':
        snapshot['updates'][0]['actor_key'] = 'member:2:2'
    else:
        snapshot['models']['member:0:0']['log_likelihood'][0] += 1
    sharing.packed_write(directory/relative,snapshot)
    rehash(directory,relative)
    with pytest.raises(ValueError,match=match):
        sharing.verify(directory)


@pytest.mark.parametrize('mutation,match',[
    ('missing_checkpoint','Checkpoint identity grid'),
    ('checkpoint_count','Checkpoint counts'),
    ('prediction_target','Probe target'),
    ('parameter_truth','Parameter truth'),
])
def test_scored_grid_tampering_fails_after_checksum_rewrite(tiny_sharing,tmp_path,mutation,match):
    directory = copy_study(tiny_sharing,tmp_path)
    name = 'predictions.csv.gz' if mutation == 'prediction_target' else (
        'parameters.csv' if mutation == 'parameter_truth' else 'checkpoints.csv')
    relative = f'cases/{tiny_sharing[1]["cases"][0]["arena_id"]}/{name}'
    rows = sharing.csv_read(directory/relative)
    if mutation == 'missing_checkpoint':
        rows.pop()
    else:
        field = {'checkpoint_count':'unique_observations','prediction_target':'target',
                 'parameter_truth':'true_value'}[mutation]
        rows[0][field] = str(int(rows[0][field])+1) if mutation == 'checkpoint_count' else str(float(rows[0][field])+1)
    sharing.csv_write(directory/relative,rows)
    rehash(directory,relative)
    with pytest.raises(ValueError,match=match):
        sharing.verify(directory)


def test_aggregate_export_tampering_is_rejected(tiny_sharing,tmp_path):
    directory = copy_study(tiny_sharing,tmp_path)
    rows = sharing.csv_read(directory/'transport.csv')
    rows[0]['sent_bytes'] = 999
    sharing.csv_write(directory/'transport.csv',rows)
    rehash(directory,'transport.csv')
    with pytest.raises(ValueError,match='Exported transport'):
        sharing.verify(directory)


def test_paired_summary_tampering_is_rejected(tiny_sharing,tmp_path):
    directory = copy_study(tiny_sharing,tmp_path)
    summary = json.loads((directory/'summary.json').read_text())
    summary['paired_contrasts'][0]['crps_aulc_ticks']['mean'] += 1
    sharing.json_write(directory/'summary.json',summary)
    rehash(directory,'summary.json')
    with pytest.raises(ValueError,match='Paired arena summary reconstruction'):
        sharing.verify(directory)
