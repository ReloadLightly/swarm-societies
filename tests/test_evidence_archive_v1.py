"""Archive integrity, bounded streaming, nonreplacement and download recovery."""
from contextlib import contextmanager
import gzip
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import threading
import tracemalloc
from unittest.mock import patch

import pytest

from swarm_societies import evidence_archive_v1 as bundles


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def fixture(directory, files=None):
    root = directory / 'original'
    root.mkdir()
    files = files or {'evidence/a.bin': b'alpha', 'evidence/sub/b.bin': b'beta',
                      'evidence/empty': b''}
    entries = []
    for name, data in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entries.append({'path': name, 'size': len(data), 'sha256': sha(data)})
    inventory, archive, manifest = (directory / name for name in ('inventory.json', 'bundle.tar.gz', 'bundle.json'))
    write_json(inventory, {'version': bundles.INVENTORY_VERSION, 'files': entries})
    bundles.package(root, inventory, archive, manifest, source_url='https://example.invalid/bundle.tar.gz')
    return root, inventory, archive, manifest


def replace_archive(archive, manifest, raw):
    with archive.open('wb') as output, gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as stream:
        stream.write(raw)
    value = json.loads(manifest.read_text())
    data = archive.read_bytes()
    value['archive'].update(size=len(data), sha256=sha(data))
    write_json(manifest, value)


def test_deterministic_archive_metadata_and_exact_repeated_restore(tmp_path):
    root, inventory, archive, manifest = fixture(tmp_path)
    first = archive.read_bytes()
    for path in root.rglob('*'):
        if path.is_file():
            path.chmod(0o600)
            os.utime(path, (12345, 54321))
    second = tmp_path / 'different-name.tar.gz'
    bundles.package(root, inventory, second, tmp_path / 'second.json')
    assert second.read_bytes() == first
    with tarfile.open(archive, 'r:gz') as handle:
        members = handle.getmembers()
        assert [row.name for row in members] == sorted(row.name for row in members)
        assert all(row.isfile() and row.uid == row.gid == row.mtime == 0 and row.mode == 0o644 for row in members)
        assert all(not row.pax_headers and not row.linkname for row in members)
    destination = tmp_path / 'restored'
    destination.mkdir()
    result = bundles.restore(manifest, archive, destination)
    assert (result['restored'], result['existing'], result['file_count']) == (3, 0, 3)
    for entry in json.loads(manifest.read_text())['files']:
        target = destination / entry['path']
        assert target.read_bytes() == (root / entry['path']).read_bytes()
        assert target.stat().st_mode & 0o777 == 0o644
    stats = {path: (path.stat().st_ino, path.stat().st_mtime_ns) for path in destination.rglob('*') if path.is_file()}
    again = bundles.restore(manifest, archive, destination)
    assert (again['restored'], again['existing']) == (0, 3)
    assert stats == {path: (path.stat().st_ino, path.stat().st_mtime_ns) for path in stats}
    assert bundles.verify(manifest, archive)['total_file_bytes'] == 9


def test_package_never_replaces_outputs_and_rejects_changed_sources(tmp_path):
    root, inventory, archive, manifest = fixture(tmp_path)
    before = archive.read_bytes(), manifest.read_bytes()
    with pytest.raises(FileExistsError):
        bundles.package(root, inventory, archive, manifest)
    assert before == (archive.read_bytes(), manifest.read_bytes())
    (root / 'evidence/a.bin').write_bytes(b'wrong')
    with pytest.raises(bundles.ArchiveError, match='differs'):
        bundles.package(root, inventory, tmp_path / 'new.tar.gz', tmp_path / 'new.json')
    assert not (tmp_path / 'new.tar.gz').exists()
    assert not (tmp_path / 'new.json').exists()
    assert not list(tmp_path.glob('.evidence-*'))


@pytest.mark.parametrize('path', ['/absolute', '../escape', 'a/../b', 'a//b', './a',
                                  'a\\b', 'C:drive', 'a\nb', 'a/'])
def test_inventory_path_traversal_and_noncanonical_paths_rejected(tmp_path, path):
    root = tmp_path / 'root'
    root.mkdir()
    inventory = tmp_path / 'inventory.json'
    write_json(inventory, {'version': bundles.INVENTORY_VERSION,
                          'files': [{'path': path, 'size': 0, 'sha256': sha(b'')}]})
    with pytest.raises(bundles.ArchiveError):
        bundles.package(root, inventory, tmp_path / 'out.gz', tmp_path / 'out.json')
    assert not (tmp_path / 'out.gz').exists()


def test_manifest_duplicate_paths_conflicts_types_and_sizes_rejected(tmp_path):
    _, _, _, manifest = fixture(tmp_path)
    original = json.loads(manifest.read_text())
    corruptions = []
    value = json.loads(manifest.read_text())
    value['files'].append(value['files'][0])
    corruptions.append(value)
    value = json.loads(manifest.read_text())
    value['files'][0]['size'] = True
    corruptions.append(value)
    value = json.loads(manifest.read_text())
    value['archive']['filename'] = '../bundle.tar.gz'
    corruptions.append(value)
    value = json.loads(manifest.read_text())
    value['total_file_bytes'] += 1
    corruptions.append(value)
    value = json.loads(manifest.read_text())
    value['files'].append({'path': 'evidence/a.bin/child', 'size': 0, 'sha256': sha(b'')})
    corruptions.append(value)
    for value in corruptions:
        write_json(manifest, value)
        with pytest.raises(bundles.ArchiveError):
            bundles.load_manifest(manifest)
    write_json(manifest, original)
    with pytest.raises(bundles.ArchiveError, match='max_bytes'):
        bundles.load_manifest(manifest, max_bytes=1)
    manifest.write_text('{"version":"x","version":"y"}')
    with pytest.raises(bundles.ArchiveError, match='Duplicate'):
        bundles.load_manifest(manifest)


def test_archive_sha_and_inner_hashes_both_checked_before_publication(tmp_path):
    _, _, archive, manifest = fixture(tmp_path)
    destination = tmp_path / 'restored'
    destination.mkdir()
    original = archive.read_bytes()
    archive.write_bytes(original[:-4] + b'bad!')
    with pytest.raises(bundles.ArchiveError, match='SHA256'):
        bundles.restore(manifest, archive, destination)
    assert not list(destination.iterdir())
    archive.write_bytes(original)
    raw = bytearray(gzip.decompress(original))
    # Corrupt the last nonempty member, after earlier valid members were staged.
    raw[2048] ^= 1
    replace_archive(archive, manifest, raw)
    with pytest.raises(bundles.ArchiveError, match='SHA256'):
        bundles.restore(manifest, archive, destination)
    assert not list(destination.iterdir())


def test_malformed_deflate_has_a_clean_error_and_no_publication(tmp_path):
    _, _, archive, manifest = fixture(tmp_path)
    bad = bytes.fromhex('1f8b0800') + b'\0' * 6 + b'\x07' + b'\0' * 8
    archive.write_bytes(bad)
    value = json.loads(manifest.read_text())
    value['archive'].update(size=len(bad), sha256=sha(bad))
    write_json(manifest, value)
    destination = tmp_path / 'restored'
    destination.mkdir()
    with pytest.raises(bundles.ArchiveError, match='Corrupt gzip'):
        bundles.restore(manifest, archive, destination)
    assert not list(destination.iterdir())


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'directory', 'traversal', 'absolute',
                                  'duplicate', 'unexpected', 'size_bomb', 'extra_member', 'pax'])
def test_malicious_members_are_rejected_without_extracting(tmp_path, kind):
    _, _, archive, manifest = fixture(tmp_path)
    raw = bytearray(gzip.decompress(archive.read_bytes()))
    header_offset = 0
    member = tarfile.TarInfo.frombuf(bytes(raw[:512]), 'utf-8', 'strict')
    if kind in ('symlink', 'hardlink'):
        member.type = tarfile.SYMTYPE if kind == 'symlink' else tarfile.LNKTYPE
        member.linkname = '../../outside'
    elif kind == 'directory':
        member.type = tarfile.DIRTYPE
    elif kind == 'traversal':
        member.name = '../outside'
    elif kind == 'absolute':
        member.name = '/outside'
    elif kind == 'duplicate':
        header_offset = 1024
    elif kind == 'unexpected':
        member.name = 'evidence/unknown'
    elif kind == 'size_bomb':
        member.size = 4 * 1024**3
    elif kind == 'extra_member':
        header_offset = 2560
    elif kind == 'pax':
        member.type = tarfile.XHDTYPE
        member.size = 1000000000
    raw[header_offset:header_offset + 512] = member.tobuf(format=tarfile.USTAR_FORMAT)
    replace_archive(archive, manifest, raw)
    destination = tmp_path / 'restored'
    destination.mkdir()
    with pytest.raises((bundles.ArchiveError, ValueError)):
        bundles.restore(manifest, archive, destination)
    assert not list(destination.iterdir())
    assert not (tmp_path / 'outside').exists()


def test_late_existing_conflict_prevents_every_publication(tmp_path):
    _, _, archive, manifest = fixture(tmp_path)
    destination = tmp_path / 'restored'
    (destination / 'evidence/sub').mkdir(parents=True)
    incumbent = destination / 'evidence/sub/b.bin'
    incumbent.write_bytes(b'incumbent must survive')
    with pytest.raises(bundles.ArchiveError, match='Existing destination differs'):
        bundles.restore(manifest, archive, destination)
    assert incumbent.read_bytes() == b'incumbent must survive'
    assert not (destination / 'evidence/a.bin').exists()
    assert not (destination / 'evidence/empty').exists()
    assert not list(destination.glob('.evidence-*'))


def test_source_and_destination_symlinks_are_rejected(tmp_path):
    root, inventory, archive, manifest = fixture(tmp_path)
    outside = tmp_path / 'outside'
    outside.mkdir()
    destination = tmp_path / 'restored'
    destination.mkdir()
    (destination / 'evidence').symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        bundles.restore(manifest, archive, destination)
    assert not list(outside.iterdir())
    (root / 'evidence/a.bin').unlink()
    (root / 'evidence/a.bin').symlink_to(archive)
    with pytest.raises(OSError):
        bundles.package(root, inventory, tmp_path / 'bad.gz', tmp_path / 'bad.json')
    assert not (tmp_path / 'bad.gz').exists()


def test_publication_race_never_overwrites_a_new_conflicting_file(tmp_path):
    _, _, archive, manifest = fixture(tmp_path)
    destination = tmp_path / 'restored'
    destination.mkdir()
    original = bundles._publish_member

    def race(root_descriptor, entry, staged):
        target = destination / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'concurrent writer')
        return original(root_descriptor, entry, staged)

    with patch.object(bundles, '_publish_member', side_effect=race):
        with pytest.raises(bundles.ArchiveError):
            bundles.restore(manifest, archive, destination)
    assert (destination / 'evidence/a.bin').read_bytes() == b'concurrent writer'
    assert not list(destination.rglob('.evidence-file-*'))


def test_large_member_is_streamed_in_bounded_memory(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    source = root / 'large.bin'
    block = b'0123456789abcdef' * 4096
    digest = hashlib.sha256()
    with source.open('wb') as output:
        for _ in range(512):
            output.write(block)
            digest.update(block)
    inventory, archive, manifest = (tmp_path / name for name in ('inventory.json', 'big.gz', 'big.json'))
    write_json(inventory, {'version': bundles.INVENTORY_VERSION, 'files': [
        {'path': 'large.bin', 'size': 32 * 1024**2, 'sha256': digest.hexdigest()}]})
    tracemalloc.start()
    try:
        bundles.package(root, inventory, archive, manifest)
        assert bundles.verify(manifest, archive)['total_file_bytes'] == 32 * 1024**2
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 8 * 1024**2


@contextmanager
def server(body, mode='normal'):
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            requests.append(dict(self.headers))
            range_header = self.headers.get('Range')
            offset = int(range_header.split('=')[1].split('-')[0]) if range_header else 0
            status = 206 if range_header and mode != 'ignore_range' else 200
            if status == 200:
                offset = 0
            self.send_response(status)
            self.send_header('ETag', '"changed"' if range_header and mode == 'bad_etag' else '"fixture-v1"')
            if status == 206:
                start = offset + 1 if mode == 'bad_range' else offset
                self.send_header('Content-Range', f'bytes {start}-{len(body)-1}/{len(body)}')
            if mode != 'no_length':
                self.send_header('Content-Length', str(len(body) - offset + (1 if mode == 'bad_length' else 0)))
            self.end_headers()
            if len(requests) == 1 and mode in ('interrupt', 'ignore_range', 'bad_etag', 'bad_range'):
                self.wfile.write(body[:len(body)//3])
                self.wfile.flush()
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
            else:
                try:
                    self.wfile.write(body[offset:])
                except (BrokenPipeError, ConnectionResetError):
                    pass

    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_port}/bundle.tar.gz', requests
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def http_fixture(tmp_path, mode='normal'):
    return fixture(tmp_path, {'evidence/random.bin': os.urandom(192 * 1024)})


def set_url(manifest, url):
    value = json.loads(manifest.read_text())
    value['source_url'] = url
    write_json(manifest, value)
    return value['archive']['sha256']


@pytest.mark.parametrize('mode', ['interrupt', 'ignore_range'])
def test_download_resumes_with_validated_range_or_restarts_complete_response(tmp_path, mode):
    _, _, archive, manifest = http_fixture(tmp_path)
    body, cache = archive.read_bytes(), tmp_path / 'cache'
    with server(body, mode) as (url, requests):
        digest = set_url(manifest, url)
        with pytest.raises(bundles.ArchiveError, match='Interrupted|interrupted'):
            bundles.fetch(manifest, cache, allow_http_for_tests=True)
        partial = cache / (digest + '.part')
        offset = partial.stat().st_size
        assert 0 < offset < len(body)
        assert not (cache / (digest + '.tar.gz')).exists()
        final = bundles.fetch(manifest, cache, allow_http_for_tests=True)
        assert final.read_bytes() == body
        assert requests[1]['Range'] == f'bytes={offset}-'
        assert requests[1]['If-Range'] == '"fixture-v1"'
        assert not partial.exists()
        assert not (cache / (digest + '.part.json')).exists()
        assert bundles.fetch(manifest, cache, offline=True, allow_http_for_tests=True) == final
        assert len(requests) == 2


@pytest.mark.parametrize('mode', ['bad_range', 'bad_etag'])
def test_invalid_resume_does_not_append_or_publish(tmp_path, mode):
    _, _, archive, manifest = http_fixture(tmp_path)
    cache = tmp_path / 'cache'
    with server(archive.read_bytes(), mode) as (url, _):
        digest = set_url(manifest, url)
        with pytest.raises(bundles.ArchiveError):
            bundles.fetch(manifest, cache, allow_http_for_tests=True)
        partial = cache / (digest + '.part')
        saved = partial.read_bytes()
        with pytest.raises(bundles.ArchiveError, match='Range|validator'):
            bundles.fetch(manifest, cache, allow_http_for_tests=True)
        assert partial.read_bytes() == saved
        assert not (cache / (digest + '.tar.gz')).exists()


@pytest.mark.parametrize('mode', ['no_length', 'bad_length'])
def test_download_requires_exact_content_length_before_writing(tmp_path, mode):
    _, _, archive, manifest = http_fixture(tmp_path)
    cache = tmp_path / 'cache'
    with server(archive.read_bytes(), mode) as (url, _):
        digest = set_url(manifest, url)
        with pytest.raises(bundles.ArchiveError, match='Content-Length'):
            bundles.fetch(manifest, cache, allow_http_for_tests=True)
        assert not (cache / (digest + '.part')).exists()
        assert not (cache / (digest + '.tar.gz')).exists()


def test_http_requires_explicit_loopback_test_permission(tmp_path):
    _, _, archive, manifest = fixture(tmp_path)
    with server(archive.read_bytes()) as (url, requests):
        set_url(manifest, url)
        with pytest.raises(bundles.ArchiveError, match='HTTPS'):
            bundles.fetch(manifest, tmp_path / 'cache')
        assert requests == []
    set_url(manifest, 'http://example.com/bundle.tar.gz')
    with pytest.raises(bundles.ArchiveError, match='HTTPS'):
        bundles.fetch(manifest, tmp_path / 'cache', allow_http_for_tests=True)


def test_offline_cache_verifies_bytes_and_never_uses_network(tmp_path):
    _, _, archive, manifest = fixture(tmp_path)
    cache = tmp_path / 'cache'
    cache.mkdir()
    value = json.loads(manifest.read_text())
    target = cache / (value['archive']['sha256'] + '.tar.gz')
    with patch.object(bundles.urllib.request, 'build_opener', side_effect=AssertionError('No network')):
        with pytest.raises(bundles.ArchiveError, match='offline'):
            bundles.fetch(manifest, cache, offline=True)
        target.write_bytes(archive.read_bytes())
        assert bundles.fetch(manifest, cache, offline=True) == target
        target.write_bytes(b'corrupt cached bytes')
        with pytest.raises(bundles.ArchiveError):
            bundles.fetch(manifest, cache, offline=True)
        assert target.read_bytes() == b'corrupt cached bytes'


def test_mutable_download_partial_cannot_alias_an_incumbent_hardlink(tmp_path):
    _, _, archive, manifest = fixture(tmp_path)
    cache = tmp_path / 'cache'
    cache.mkdir()
    value = json.loads(manifest.read_text())
    digest = value['archive']['sha256']
    incumbent = tmp_path / 'incumbent.bin'
    incumbent.write_bytes(archive.read_bytes()[:50])
    partial = cache / (digest + '.part')
    os.link(incumbent, partial)
    write_json(cache / (digest + '.part.json'), {
        'version': 'evidence-download-part-v1', 'archive_sha256': digest,
        'archive_size': value['archive']['size'], 'source_url': value['source_url'],
        'validator': {'kind': 'etag', 'value': '"fixture-v1"'}})
    before = incumbent.read_bytes()
    with patch.object(bundles.urllib.request, 'build_opener', side_effect=AssertionError('No network')):
        with pytest.raises(bundles.ArchiveError, match='hard link'):
            bundles.fetch(manifest, cache)
    assert incumbent.read_bytes() == partial.read_bytes() == before


@pytest.mark.parametrize('url', ['http://example.com/archive', 'file:///tmp/archive',
                                'https://name:secret@example.com/archive',
                                'https://example.com/archive#fragment'])
def test_production_download_urls_and_redirects_cannot_downgrade(tmp_path, url):
    _, _, _, manifest = fixture(tmp_path)
    set_url(manifest, url)
    with pytest.raises(bundles.ArchiveError):
        bundles.load_manifest(manifest)
    request = bundles.urllib.request.Request('https://example.com/start')
    with pytest.raises(bundles.ArchiveError):
        bundles._HTTPSRedirect(False).redirect_request(request, None, 302, 'found', {}, url)


def test_bad_download_hash_never_publishes_verified_cache_name(tmp_path):
    _, _, archive, manifest = http_fixture(tmp_path)
    wrong = bytearray(archive.read_bytes())
    wrong[50] ^= 1
    cache = tmp_path / 'cache'
    with server(wrong) as (url, _):
        digest = set_url(manifest, url)
        with pytest.raises(bundles.ArchiveError, match='SHA256'):
            bundles.fetch(manifest, cache, allow_http_for_tests=True)
        assert not (cache / (digest + '.tar.gz')).exists()


def test_cli_verifies_and_restores_an_existing_repo(tmp_path):
    _, _, archive, manifest = fixture(tmp_path)
    root = tmp_path / 'restored'
    root.mkdir()
    script = Path(__file__).resolve().parents[1] / 'scripts/evidence_archive_v1.py'
    result = subprocess.run([sys.executable, str(script), 'restore', '--manifest', str(manifest),
                             '--archive', str(archive), '--root', str(root)],
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['restored'] == 3
