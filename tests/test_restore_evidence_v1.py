"""Repository restoration validates its catalog and preserves existing evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts import restore_evidence_v1 as cli
from swarm_societies import evidence_archive_v1 as archive


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def bundle(tmp_path):
    source, catalog_dir, checkout, cache = (tmp_path / name for name in ('source', 'catalog', 'checkout', 'cache'))
    for path in (source, catalog_dir, checkout, cache):
        path.mkdir()
    studies, manifests, payloads = [], {}, {}
    for study in ('alpha', 'beta'):
        files = []
        for name, data in [('a.json', (study + ' first\n').encode()), ('b.bin', bytes(range(64)))]:
            relative = f'evidence/{study}/{name}'
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            files.append({'path': relative, 'size': len(data), 'sha256': sha(target)})
            payloads[relative] = data
        inventory = tmp_path / f'{study}-inventory.json'
        write_json(inventory, {'version': archive.INVENTORY_VERSION, 'files': files})
        manifest_path = catalog_dir / f'{study}.json'
        packed = tmp_path / f'{study}.tar.gz'
        manifest = archive.package(source, inventory, packed, manifest_path,
            source_url=f'https://example.invalid/{study}.tar.gz')
        shutil.copyfile(packed, cache / (manifest['archive']['sha256'] + '.tar.gz'))
        manifests[study] = manifest_path
        studies.append({'id': study, 'manifest': manifest_path.name, 'manifest_sha256': sha(manifest_path)})
    catalog = catalog_dir / 'catalog.json'
    write_json(catalog, {'version': 'evidence-catalog-v1', 'studies': studies})
    return {'catalog': catalog, 'checkout': checkout, 'cache': cache,
            'source': source, 'payloads': payloads, 'manifests': manifests}


def args(bundle, *extra):
    return ['--catalog', str(bundle['catalog']), '--root', str(bundle['checkout']),
            '--cache', str(bundle['cache']), *extra]


def populate(bundle, study=None):
    for relative, data in bundle['payloads'].items():
        if study is None or Path(relative).parts[1] == study:
            path = bundle['checkout'] / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)


def no_fetch(monkeypatch):
    monkeypatch.setattr(cli, 'fetch', lambda *a, **kw: pytest.fail('unexpected archive fetch'))


def rewrite_catalog(bundle, mutate):
    data = json.loads(bundle['catalog'].read_text())
    mutate(data)
    write_json(bundle['catalog'], data)


def test_catalog_requires_unique_studies_and_pinned_manifests(bundle):
    assert [r['id'] for r in cli.load_catalog(bundle['catalog'])['studies']] == ['alpha', 'beta']
    rewrite_catalog(bundle, lambda data: data['studies'].append(deepcopy(data['studies'][0])))
    with pytest.raises(ValueError, match='duplicated'):
        cli.load_catalog(bundle['catalog'])


@pytest.mark.parametrize('reference', ['../escaped.json', '/absolute.json', 'sub/../alpha.json'])
def test_catalog_rejects_nonportable_or_escaping_manifest_paths(bundle, reference):
    outside = bundle['catalog'].parent.parent / 'escaped.json'
    shutil.copyfile(bundle['manifests']['alpha'], outside)
    (bundle['catalog'].parent / 'sub').mkdir()
    rewrite_catalog(bundle, lambda data: data['studies'][0].update(manifest=reference))
    with pytest.raises(ValueError, match='[Mm]anifest path'):
        cli.load_catalog(bundle['catalog'])
    assert cli.main(args(bundle, '--check')) == 1


def test_catalog_rejects_symlink_escape_even_with_correct_manifest_hash(bundle):
    outside = bundle['catalog'].parent.parent / 'outside.json'
    shutil.copyfile(bundle['manifests']['alpha'], outside)
    linked = bundle['catalog'].parent / 'linked.json'
    linked.symlink_to(outside)
    rewrite_catalog(bundle, lambda data: data['studies'][0].update(manifest=linked.name))
    with pytest.raises(ValueError, match='manifest path'):
        cli.load_catalog(bundle['catalog'])


def test_catalog_rejects_changed_manifest_before_fetch(bundle, monkeypatch):
    no_fetch(monkeypatch)
    bundle['manifests']['alpha'].write_text('{}')
    with pytest.raises(ValueError, match='checksum'):
        cli.load_catalog(bundle['catalog'])
    assert cli.main(args(bundle)) == 1
    assert not list(bundle['checkout'].iterdir())


@pytest.mark.parametrize('catalog', [[], None, 'catalog', {'version': 'wrong', 'studies': []}])
def test_malformed_catalog_returns_failure_instead_of_uncaught_exception(bundle, catalog):
    write_json(bundle['catalog'], catalog)
    assert cli.main(args(bundle, '--check')) == 1


def test_repository_catalog_refuses_generic_archive_targets_outside_evidence(bundle, monkeypatch):
    manifest = json.loads(bundle['manifests']['alpha'].read_text())
    manifest['files'][0]['path'] = 'docs/a.json'
    write_json(bundle['manifests']['alpha'], manifest)
    rewrite_catalog(bundle, lambda data: data['studies'][0].update(manifest_sha256=sha(bundle['manifests']['alpha'])))
    no_fetch(monkeypatch)
    assert cli.main(args(bundle)) == 1
    assert not list(bundle['checkout'].iterdir())


def test_selected_study_does_not_require_unselected_local_files(bundle, monkeypatch, capsys):
    populate(bundle, 'beta')
    no_fetch(monkeypatch)
    assert cli.main(args(bundle, '--study', 'beta', '--check')) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [row['study'] for row in rows] == ['beta']
    assert rows[0]['checked_worktree'] and rows[0]['existing'] == 2
    assert not (bundle['checkout'] / 'evidence/alpha').exists()


@pytest.mark.parametrize('selection', [[], ['--study', 'all'], ['--study', 'beta', 'alpha']])
def test_default_all_and_explicit_selection_preserve_catalog_order(bundle, monkeypatch, capsys, selection):
    populate(bundle)
    no_fetch(monkeypatch)
    assert cli.main(args(bundle, *selection)) == 0
    assert [json.loads(line)['study'] for line in capsys.readouterr().out.splitlines()] == ['alpha', 'beta']


@pytest.mark.parametrize('selection', [['unknown'], ['all', 'alpha']])
def test_unknown_or_mixed_all_selection_fails_before_work(bundle, monkeypatch, selection):
    no_fetch(monkeypatch)
    monkeypatch.setattr(cli, 'check_restored', lambda *a: pytest.fail('unknown selection checked files'))
    assert cli.main(args(bundle, '--study', *selection)) == 1


def test_check_missing_evidence_uses_no_network_and_writes_nothing(bundle, monkeypatch):
    no_fetch(monkeypatch)
    assert cli.main(args(bundle, '--check', '--study', 'alpha')) == 1
    assert not list(bundle['checkout'].iterdir())


@pytest.mark.parametrize('mutation', ['same_size_corruption', 'wrong_size', 'directory', 'symlink'])
def test_existing_corrupt_evidence_fails_without_fetch_or_overwrite(bundle, monkeypatch, mutation):
    populate(bundle, 'alpha')
    path = bundle['checkout'] / 'evidence/alpha/a.json'
    if mutation == 'same_size_corruption': path.write_bytes(b'x' * path.stat().st_size)
    if mutation == 'wrong_size': path.write_bytes(b'x')
    if mutation == 'directory': path.unlink(); path.mkdir()
    if mutation == 'symlink': path.unlink(); path.symlink_to(bundle['source'] / 'evidence/alpha/a.json')
    before = None if path.is_dir() else path.read_bytes()
    no_fetch(monkeypatch)
    assert cli.main(args(bundle, '--study', 'alpha')) == 1
    if mutation == 'directory': assert path.is_dir()
    elif mutation == 'symlink': assert path.is_symlink()
    else: assert path.read_bytes() == before


def test_offline_cached_restoration_preserves_identical_files_and_records_receipt(bundle, monkeypatch, tmp_path):
    relative = 'evidence/alpha/a.json'
    existing = bundle['checkout'] / relative
    existing.parent.mkdir(parents=True)
    existing.write_bytes(bundle['payloads'][relative])
    inode = existing.stat().st_ino
    monkeypatch.setattr(archive.urllib.request, 'build_opener', lambda *a: pytest.fail('offline network request'))
    receipt = tmp_path / 'receipts/restored.json'
    assert cli.main(args(bundle, '--study', 'alpha', '--offline', '--receipt', str(receipt))) == 0
    result = json.loads(receipt.read_text())
    assert result['catalog_sha256'] == sha(bundle['catalog'])
    assert result['offline'] and result['status'] == 'ok'
    assert result['studies'][0]['restored'] == result['studies'][0]['existing'] == 1
    assert existing.stat().st_ino == inode
    for relative, data in bundle['payloads'].items():
        if Path(relative).parts[1] == 'alpha':
            assert (bundle['checkout'] / relative).read_bytes() == data
    no_fetch(monkeypatch)
    assert cli.main(args(bundle, '--study', 'alpha', '--offline')) == 0


def test_missing_first_file_and_later_conflict_publishes_nothing(bundle):
    conflict = bundle['checkout'] / 'evidence/alpha/b.bin'
    conflict.parent.mkdir(parents=True)
    conflict.write_bytes(b'corrupt')
    assert cli.main(args(bundle, '--study', 'alpha', '--offline')) == 1
    assert conflict.read_bytes() == b'corrupt'
    assert not (conflict.parent / 'a.json').exists()


def test_offline_uncached_archive_is_explicit_failure_without_partial_evidence(bundle, monkeypatch):
    for path in bundle['cache'].iterdir(): path.unlink()
    monkeypatch.setattr(archive.urllib.request, 'build_opener', lambda *a: pytest.fail('offline network request'))
    assert cli.main(args(bundle, '--study', 'alpha', '--offline')) == 1
    assert not list(bundle['checkout'].iterdir())


def test_verify_only_checks_cached_archive_without_restoring(bundle, monkeypatch, capsys):
    monkeypatch.setattr(archive.urllib.request, 'build_opener', lambda *a: pytest.fail('offline network request'))
    assert cli.main(args(bundle, '--study', 'beta', '--offline', '--verify-only')) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'ok'
    assert not list(bundle['checkout'].iterdir())
    assert cli.main(args(bundle, '--verify-only', '--check')) == 1


def test_standalone_cli_restores_from_offline_cache(bundle):
    completed = subprocess.run([sys.executable, str(Path(cli.__file__).resolve()),
        *args(bundle, '--study', 'alpha', '--offline')], capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result['study'] == 'alpha' and result['restored'] == 2
    for relative, data in bundle['payloads'].items():
        if Path(relative).parts[1] == 'alpha':
            assert (bundle['checkout'] / relative).read_bytes() == data


@pytest.mark.parametrize('symlink', [False, True])
def test_existing_receipt_is_rejected_before_any_work(bundle, monkeypatch, tmp_path, symlink):
    receipt = tmp_path / 'receipt.json'
    target = tmp_path / 'keep.json'
    target.write_bytes(b'preserve')
    if symlink: receipt.symlink_to(target)
    else: receipt.write_bytes(b'preserve')
    no_fetch(monkeypatch)
    monkeypatch.setattr(cli, 'check_restored', lambda *a: pytest.fail('existing receipt triggered work'))
    assert cli.main(args(bundle, '--receipt', str(receipt))) == 1
    assert receipt.read_bytes() == target.read_bytes() == b'preserve'
