"""Deterministic, streaming evidence bundles and verified, nonreplacing restore.

Version 1 accepts only canonical USTAR regular-file members inside gzip. It
never calls tar extraction helpers. A restore stages and verifies every member
and preflights every destination before publishing any requested path. Existing
identical files are retained; conflicting files and symlink paths are rejected.
Publication is atomic per file, not a transaction across the whole repository.
"""
from __future__ import annotations

from contextlib import contextmanager
import email.utils
import fcntl
import gzip
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib

VERSION = 'evidence-archive-v1'
INVENTORY_VERSION = 'evidence-inventory-v1'
DEFAULT_MAX_BYTES = 1024**3
MAX_OVERRIDE_BYTES = 1024**4
MAX_MANIFEST_BYTES = 16 * 1024**2
MAX_FILES = 100000
CHUNK = 64 * 1024
SHA_PATTERN = re.compile(r'[0-9a-f]{64}\Z')


class ArchiveError(ValueError):
    """Invalid or unsafe archive, manifest, destination or download response."""


def _limit(value):
    if type(value) is not int or not 1 <= value <= MAX_OVERRIDE_BYTES:
        raise ArchiveError('max_bytes must be an integer from 1 byte through 1 TiB')
    return value


def _path(value):
    if (type(value) is not str or not value or '\\' in value or ':' in value or
            any(ord(char) < 32 or ord(char) == 127 for char in value) or
            any(part in ('', '.', '..') for part in value.split('/'))):
        raise ArchiveError('Archive paths must be canonical repository-relative POSIX paths')
    return value


def _url(value, allow_http_for_tests=False):
    if value is None:
        return None
    if type(value) is not str or len(value) > 8192 or any(ord(c) < 33 for c in value):
        raise ArchiveError('Invalid archive source URL')
    try:
        parsed = urllib.parse.urlsplit(value)
        _ = parsed.port
    except ValueError as exc:
        raise ArchiveError('Invalid archive source URL') from exc
    allowed = parsed.scheme == 'https'
    if allow_http_for_tests and parsed.scheme == 'http':
        allowed = parsed.hostname in ('127.0.0.1', 'localhost', '::1')
    if (not allowed or not parsed.hostname or parsed.username is not None or
            parsed.password is not None or parsed.fragment):
        raise ArchiveError('Archive source and redirects require HTTPS without credentials or fragments')
    return value


def _object(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ArchiveError('Duplicate JSON object key')
        output[key] = value
    return output


@contextmanager
def _directory(path):
    """Open every existing directory component without following symlinks."""
    absolute = Path(path).absolute()
    descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in absolute.parts[1:]:
            if part in ('.', '..'):
                raise ArchiveError('Directory paths cannot contain dot components')
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def _parent(root_descriptor, relative, *, create=False):
    parts = _path(relative).split('/')
    descriptor = os.dup(root_descriptor)
    try:
        for part in parts[:-1]:
            if create:
                try:
                    os.mkdir(part, 0o755, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor, parts[-1]
    finally:
        os.close(descriptor)


@contextmanager
def _regular(path):
    path = Path(path).absolute()
    with _directory(path.parent) as parent:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ArchiveError('Expected a regular nonsymlink file: ' + str(path))
        with os.fdopen(descriptor, 'rb', closefd=False) as handle:
            yield handle
    finally:
        os.close(descriptor)


def _read_json(path, limit=MAX_MANIFEST_BYTES):
    with _regular(path) as handle:
        size = os.fstat(handle.fileno()).st_size
        if size > limit:
            raise ArchiveError('JSON file exceeds byte limit')
        data = handle.read(size + 1)
        if len(data) != size or os.fstat(handle.fileno()).st_size != size:
            raise ArchiveError('JSON file changed during bounded read')
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ArchiveError('Nonfinite JSON')))
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ArchiveError('Malformed JSON input') from exc
    return value, hashlib.sha256(data).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, allow_nan=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def _header(entry):
    info = tarfile.TarInfo(entry['path'])
    info.size, info.mode, info.uid, info.gid, info.mtime = entry['size'], 0o644, 0, 0, 0
    info.uname = info.gname = ''
    info.type = tarfile.REGTYPE
    try:
        return info.tobuf(format=tarfile.USTAR_FORMAT, encoding='utf-8', errors='strict')
    except (ValueError, UnicodeError) as exc:
        raise ArchiveError('Path cannot be represented in canonical USTAR: ' + entry['path']) from exc


def _entries(values, maximum, *, sorted_required=False):
    if type(values) is not list or not 1 <= len(values) <= MAX_FILES:
        raise ArchiveError('Inventory requires 1 to 100000 regular files')
    result, total, names = [], 0, set()
    for value in values:
        if type(value) is not dict or set(value) != {'path', 'size', 'sha256'}:
            raise ArchiveError('Each inventory entry requires path, size and sha256 only')
        name = _path(value['path'])
        if name in names:
            raise ArchiveError('Duplicate inventory path: ' + name)
        names.add(name)
        if type(value['size']) is not int or not 0 <= value['size'] <= maximum:
            raise ArchiveError('Invalid or excessive declared file size')
        if type(value['sha256']) is not str or not SHA_PATTERN.fullmatch(value['sha256']):
            raise ArchiveError('Invalid SHA256 in file inventory')
        total += value['size']
        if total > maximum:
            raise ArchiveError('Declared file payload exceeds max_bytes')
        _header(value)
        result.append(dict(value))
    result.sort(key=lambda row: row['path'])
    for value in result:
        if any('/'.join(value['path'].split('/')[:index]) in names
               for index in range(1, len(value['path'].split('/')))):
            raise ArchiveError('Inventory contains a file/directory path conflict')
    if sorted_required and result != values:
        raise ArchiveError('Manifest file inventory is not sorted canonically')
    return result, total


def load_manifest(path, *, max_bytes=DEFAULT_MAX_BYTES, allow_http_for_tests=False):
    maximum = _limit(max_bytes)
    manifest, _ = _read_json(path)
    expected = {'version', 'archive', 'files', 'total_file_bytes', 'source_url', 'inventory_sha256'}
    if type(manifest) is not dict or set(manifest) != expected or manifest['version'] != VERSION:
        raise ArchiveError('Unsupported or malformed evidence archive manifest')
    archive = manifest['archive']
    if type(archive) is not dict or set(archive) != {'filename', 'sha256', 'size'}:
        raise ArchiveError('Malformed archive metadata')
    if '/' in _path(archive['filename']):
        raise ArchiveError('Archive filename must be a basename')
    if type(archive['size']) is not int or not 1 <= archive['size'] <= maximum:
        raise ArchiveError('Compressed archive exceeds max_bytes or has invalid size')
    if type(archive['sha256']) is not str or not SHA_PATTERN.fullmatch(archive['sha256']):
        raise ArchiveError('Invalid archive SHA256')
    if type(manifest['inventory_sha256']) is not str or not SHA_PATTERN.fullmatch(manifest['inventory_sha256']):
        raise ArchiveError('Invalid inventory SHA256')
    _, total = _entries(manifest['files'], maximum, sorted_required=True)
    if type(manifest['total_file_bytes']) is not int or total != manifest['total_file_bytes']:
        raise ArchiveError('Manifest total file bytes differs from inventory')
    _url(manifest['source_url'], allow_http_for_tests)
    return manifest


def _hash_handle(handle, expected_size):
    if os.fstat(handle.fileno()).st_size != expected_size:
        raise ArchiveError('File size differs from inventory')
    digest, count = hashlib.sha256(), 0
    while True:
        block = handle.read(min(CHUNK, expected_size - count + 1))
        if not block:
            break
        count += len(block)
        if count > expected_size:
            raise ArchiveError('File grew beyond its declared size')
        digest.update(block)
    if count != expected_size:
        raise ArchiveError('Truncated file')
    return digest.hexdigest()


def _check_destination(root_descriptor, entry):
    try:
        with _parent(root_descriptor, entry['path']) as (parent, name):
            descriptor = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=parent)
    except FileNotFoundError:
        return False
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ArchiveError('Destination is not a regular file: ' + entry['path'])
        with os.fdopen(descriptor, 'rb', closefd=False) as handle:
            if _hash_handle(handle, entry['size']) != entry['sha256']:
                raise ArchiveError('Existing destination differs: ' + entry['path'])
    except ArchiveError as exc:
        raise ArchiveError('Existing destination differs: ' + entry['path']) from exc
    finally:
        os.close(descriptor)
    return True


def _new_output(path):
    path = Path(path).absolute()
    with _directory(path.parent) as parent:
        try:
            os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return path
    raise FileExistsError('Refusing to replace existing output: ' + str(path))


def _publish_temporary(temporary, destination):
    with _directory(Path(destination).parent) as parent:
        os.link(temporary, Path(destination).name, dst_dir_fd=parent, follow_symlinks=False)
        os.fsync(parent)


class _CompressedWriter:
    def __init__(self, handle, maximum):
        self.handle, self.maximum = handle, maximum
        self.size, self.digest = 0, hashlib.sha256()

    def write(self, data):
        if len(data) > self.maximum - self.size:
            raise ArchiveError('Compressed archive exceeds max_bytes')
        self.handle.write(data)
        self.digest.update(data)
        self.size += len(data)
        return len(data)

    def flush(self):
        self.handle.flush()


def package(root, inventory_path, output_path, manifest_path, *, source_url=None,
            max_bytes=DEFAULT_MAX_BYTES):
    """Write new deterministic archive/manifest files from a hashed inventory."""
    maximum = _limit(max_bytes)
    _url(source_url)
    inventory, inventory_sha = _read_json(inventory_path)
    if (type(inventory) is not dict or set(inventory) != {'version', 'files'} or
            inventory['version'] != INVENTORY_VERSION):
        raise ArchiveError('Unsupported or malformed file inventory')
    files, total = _entries(inventory['files'], maximum)
    output, destination = _new_output(output_path), _new_output(manifest_path)
    if output == destination:
        raise ArchiveError('Archive and manifest must have different output paths')
    _path(output.name)
    archive_temp = manifest_temp = None
    try:
        descriptor, archive_temp = tempfile.mkstemp(prefix='.evidence-archive-', dir=output.parent)
        with _directory(root) as root_descriptor, os.fdopen(descriptor, 'wb') as handle:
            writer = _CompressedWriter(handle, maximum)
            raw_size = 0
            with gzip.GzipFile(filename='', mode='wb', fileobj=writer, mtime=0, compresslevel=6) as compressed:
                for entry in files:
                    with _parent(root_descriptor, entry['path']) as (parent, name):
                        member_descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                    with os.fdopen(member_descriptor, 'rb') as member:
                        info = os.fstat(member.fileno())
                        if not stat.S_ISREG(info.st_mode) or info.st_size != entry['size']:
                            raise ArchiveError('Source is not a matching regular file: ' + entry['path'])
                        compressed.write(_header(entry))
                        digest, remaining = hashlib.sha256(), entry['size']
                        while remaining:
                            block = member.read(min(CHUNK, remaining))
                            if not block:
                                raise ArchiveError('Source was truncated: ' + entry['path'])
                            digest.update(block)
                            compressed.write(block)
                            remaining -= len(block)
                        if member.read(1) or digest.hexdigest() != entry['sha256']:
                            raise ArchiveError('Source content differs from inventory: ' + entry['path'])
                    padding = (-entry['size']) % 512
                    compressed.write(b'\0' * padding)
                    raw_size += 512 + entry['size'] + padding
                ending = 1024 + (-(raw_size + 1024)) % 10240
                compressed.write(b'\0' * ending)
            handle.flush()
            os.fsync(handle.fileno())
        manifest = {'version': VERSION, 'archive': {'filename': output.name,
                    'sha256': writer.digest.hexdigest(), 'size': writer.size},
                    'files': files, 'total_file_bytes': total, 'source_url': source_url,
                    'inventory_sha256': inventory_sha}
        descriptor, manifest_temp = tempfile.mkstemp(prefix='.evidence-manifest-', dir=destination.parent)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(_json_bytes(manifest))
            handle.flush()
            os.fsync(handle.fileno())
        _publish_temporary(archive_temp, output)
        _publish_temporary(manifest_temp, destination)
        return manifest
    finally:
        for name in (archive_temp, manifest_temp):
            if name is not None:
                os.unlink(name)


def _exact(handle, size):
    value = bytearray()
    while len(value) < size:
        block = handle.read(size - len(value))
        if not block:
            raise ArchiveError('Truncated gzip/tar stream')
        value.extend(block)
    return bytes(value)


def _scan(manifest, archive_path, staging=None):
    """Verify exact canonical headers and bytes with bounded reads, optionally stage."""
    with _regular(archive_path) as archive:
        if _hash_handle(archive, manifest['archive']['size']) != manifest['archive']['sha256']:
            raise ArchiveError('Compressed archive SHA256 differs')
        archive.seek(0)
        raw_size, seen = 0, set()
        try:
            with gzip.GzipFile(fileobj=archive, mode='rb') as stream:
                for index, entry in enumerate(manifest['files']):
                    block = _exact(stream, 512)
                    try:
                        member = tarfile.TarInfo.frombuf(block, encoding='utf-8', errors='strict')
                    except (tarfile.TarError, UnicodeError, ValueError) as exc:
                        raise ArchiveError('Invalid canonical USTAR header') from exc
                    name = _path(member.name)
                    if member.type != tarfile.REGTYPE or member.linkname:
                        raise ArchiveError('Archive contains a link or nonregular member')
                    if name in seen:
                        raise ArchiveError('Duplicate archive member: ' + name)
                    seen.add(name)
                    if name != entry['path']:
                        raise ArchiveError('Unexpected or out-of-order archive member: ' + name)
                    if member.size != entry['size']:
                        raise ArchiveError('Archive member size differs from inventory')
                    if block != _header(entry):
                        raise ArchiveError('Archive metadata is not canonical USTAR')
                    output = None
                    try:
                        if staging is not None:
                            output = (staging / str(index)).open('xb')
                        digest, remaining = hashlib.sha256(), member.size
                        while remaining:
                            data = _exact(stream, min(CHUNK, remaining))
                            digest.update(data)
                            if output is not None:
                                output.write(data)
                            remaining -= len(data)
                        if digest.hexdigest() != entry['sha256']:
                            raise ArchiveError('Archive member SHA256 differs: ' + name)
                    finally:
                        if output is not None:
                            output.close()
                    padding = (-member.size) % 512
                    if _exact(stream, padding) != b'\0' * padding:
                        raise ArchiveError('Nonzero tar member padding')
                    raw_size += 512 + member.size + padding
                ending = 1024 + (-(raw_size + 1024)) % 10240
                if _exact(stream, ending) != b'\0' * ending or stream.read(1):
                    raise ArchiveError('Unexpected archive members or trailing decompressed data')
        except (gzip.BadGzipFile, EOFError, tarfile.TarError, zlib.error) as exc:
            raise ArchiveError('Corrupt gzip/tar stream') from exc


def _receipt(manifest_path, manifest):
    _, manifest_sha = _read_json(manifest_path)
    return {'version': VERSION, 'status': 'ok', 'manifest_sha256': manifest_sha,
            'archive_sha256': manifest['archive']['sha256'], 'archive_bytes': manifest['archive']['size'],
            'file_count': len(manifest['files']), 'total_file_bytes': manifest['total_file_bytes']}


def verify(manifest_path, archive_path, *, max_bytes=DEFAULT_MAX_BYTES, allow_http_for_tests=False):
    manifest = load_manifest(manifest_path, max_bytes=max_bytes, allow_http_for_tests=allow_http_for_tests)
    _scan(manifest, archive_path)
    return _receipt(manifest_path, manifest)


def _publish_member(root_descriptor, entry, source):
    with _parent(root_descriptor, entry['path'], create=True) as (parent, name):
        temporary = '.evidence-file-' + uuid.uuid4().hex
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                             0o600, dir_fd=parent)
        try:
            with os.fdopen(descriptor, 'wb') as output, source.open('rb') as member:
                while True:
                    block = member.read(CHUNK)
                    if not block:
                        break
                    output.write(block)
                output.flush()
                os.fchmod(output.fileno(), 0o644)
                os.fsync(output.fileno())
            try:
                os.link(temporary, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            except FileExistsError:
                if _check_destination(root_descriptor, entry):
                    return False
                raise ArchiveError('Destination appeared during publication: ' + entry['path'])
            os.fsync(parent)
            return True
        finally:
            os.unlink(temporary, dir_fd=parent)


def restore(manifest_path, archive_path, root, *, max_bytes=DEFAULT_MAX_BYTES):
    manifest = load_manifest(manifest_path, max_bytes=max_bytes)
    with _directory(root) as root_descriptor:
        # Stage on the target filesystem, while keeping every final path absent.
        with tempfile.TemporaryDirectory(prefix='.evidence-restore-', dir=Path(root).absolute()) as staging:
            _scan(manifest, archive_path, Path(staging))
            existing = [_check_destination(root_descriptor, entry) for entry in manifest['files']]
            restored_count = 0
            for index, (entry, present) in enumerate(zip(manifest['files'], existing)):
                if not present and _publish_member(root_descriptor, entry, Path(staging) / str(index)):
                    restored_count += 1
    return {**_receipt(manifest_path, manifest), 'restored': restored_count,
            'existing': len(manifest['files']) - restored_count}


class _HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allow_http_for_tests):
        super().__init__()
        self.allow_http_for_tests = allow_http_for_tests

    def redirect_request(self, request, fp, code, message, headers, newurl):
        _url(newurl, self.allow_http_for_tests)
        return super().redirect_request(request, fp, code, message, headers, newurl)


def _validator(headers):
    etag = headers.get('ETag')
    if (etag and len(etag) <= 256 and etag.startswith('"') and etag.endswith('"') and
            not any(ord(c) < 32 or ord(c) == 127 for c in etag)):
        return {'kind': 'etag', 'value': etag}
    modified = headers.get('Last-Modified')
    if modified and len(modified) <= 128:
        try:
            if email.utils.parsedate_to_datetime(modified).tzinfo is not None:
                return {'kind': 'last_modified', 'value': modified}
        except (TypeError, ValueError, OverflowError):
            pass
    return None


def _cache_metadata(path, value):
    """Replace only internal resumable-download metadata, never final evidence."""
    descriptor, temporary = tempfile.mkstemp(prefix='.download-meta-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def fetch(manifest_path, cache, *, offline=False, max_bytes=DEFAULT_MAX_BYTES,
          allow_http_for_tests=False, timeout=30.0, max_download_seconds=1800.0):
    """Fetch a validated bundle to a content-addressed cache, resuming safely.

    HTTP is accepted only for explicit loopback tests. A partial download uses
    Range plus a saved strong ETag or Last-Modified If-Range validator. A server
    returning a complete 200 response restarts that partial file from byte zero.
    Only a fully verified archive is atomically published to the final cache.
    """
    manifest = load_manifest(manifest_path, max_bytes=max_bytes, allow_http_for_tests=allow_http_for_tests)
    if (type(offline) is not bool or type(timeout) not in (int, float) or not 0 < timeout <= 300 or
            type(max_download_seconds) not in (int, float) or not 0 < max_download_seconds <= 86400):
        raise ArchiveError('Invalid download/offline settings')
    cache = Path(cache).absolute()
    cache.mkdir(parents=True, exist_ok=True)
    sha, size = manifest['archive']['sha256'], manifest['archive']['size']
    destination, partial, metadata_path = (cache / (sha + suffix) for suffix in ('.tar.gz', '.part', '.part.json'))
    with _directory(cache) as directory:
        lock = os.open(sha + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,
                       0o600, dir_fd=directory)
        try:
            if not stat.S_ISREG(os.fstat(lock).st_mode):
                raise ArchiveError('Cache lock is not a regular file')
            fcntl.flock(lock, fcntl.LOCK_EX)
            if destination.exists() or destination.is_symlink():
                verify(manifest_path, destination, max_bytes=max_bytes, allow_http_for_tests=allow_http_for_tests)
                return destination
            if offline:
                raise ArchiveError('Archive is not available in the verified offline cache')
            source_url = _url(manifest['source_url'], allow_http_for_tests)
            if source_url is None:
                raise ArchiveError('Manifest has no archive source URL')
            identity = {'version': 'evidence-download-part-v1', 'archive_sha256': sha,
                        'archive_size': size, 'source_url': source_url}
            offset, saved_validator = 0, None
            if partial.exists() or partial.is_symlink():
                saved, _ = _read_json(metadata_path, 16384)
                if type(saved) is not dict or set(saved) != set(identity) | {'validator'}:
                    raise ArchiveError('Malformed partial-download metadata')
                if any(saved[key] != value for key, value in identity.items()):
                    raise ArchiveError('Partial download belongs to different inputs')
                saved_validator = saved['validator']
                if saved_validator is not None and (type(saved_validator) is not dict or
                        set(saved_validator) != {'kind', 'value'} or
                        saved_validator['kind'] not in ('etag', 'last_modified') or
                        type(saved_validator['value']) is not str or
                        any(ord(c) < 32 or ord(c) == 127 for c in saved_validator['value'])):
                    raise ArchiveError('Malformed partial-download validator')
                with _regular(partial) as handle:
                    info = os.fstat(handle.fileno())
                    if info.st_nlink != 1:
                        raise ArchiveError('Mutable partial download cannot be a hard link')
                    offset = info.st_size
                if offset > size:
                    raise ArchiveError('Partial file exceeds declared archive size')
                if offset == size:
                    verify(manifest_path, partial, max_bytes=max_bytes, allow_http_for_tests=allow_http_for_tests)
                    _publish_temporary(partial, destination)
                    partial.unlink()
                    metadata_path.unlink()
                    return destination
            elif metadata_path.exists() or metadata_path.is_symlink():
                raise ArchiveError('Partial metadata exists without its data file')
            headers = {'Accept-Encoding': 'identity', 'User-Agent': 'swarm-societies-evidence-archive-v1'}
            resume = offset > 0 and saved_validator is not None
            if resume:
                headers.update(Range=f'bytes={offset}-', **{'If-Range': saved_validator['value']})
            opener = urllib.request.build_opener(_HTTPSRedirect(allow_http_for_tests))
            started = time.monotonic()
            try:
                with opener.open(urllib.request.Request(source_url, headers=headers), timeout=timeout) as response:
                    _url(response.geturl(), allow_http_for_tests)
                    status = response.status
                    if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                        raise ArchiveError('Unexpected HTTP content encoding')
                    content_length = response.headers.get('Content-Length')
                    if content_length is None or not re.fullmatch(r'[0-9]+', content_length):
                        raise ArchiveError('Download requires an exact Content-Length')
                    current_validator = _validator(response.headers)
                    if status == 206 and resume:
                        if response.headers.get('Content-Range') != f'bytes {offset}-{size - 1}/{size}':
                            raise ArchiveError('Invalid resumed Content-Range')
                        if current_validator != saved_validator:
                            raise ArchiveError('Resumed response validator differs')
                        expected = size - offset
                    elif status == 200:
                        if response.headers.get('Content-Range') is not None:
                            raise ArchiveError('Unexpected Content-Range on complete response')
                        offset, expected = 0, size
                    else:
                        raise ArchiveError('Unexpected archive HTTP response status')
                    if int(content_length) != expected:
                        raise ArchiveError('HTTP Content-Length differs from archive inventory')
                    # Headers are validated before changing the saved partial.
                    descriptor = os.open(partial.name, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                                         0o600, dir_fd=directory)
                    try:
                        info = os.fstat(descriptor)
                        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                            raise ArchiveError('Partial download must be a regular file without hard links')
                        os.ftruncate(descriptor, offset)
                        os.lseek(descriptor, offset, os.SEEK_SET)
                        _cache_metadata(metadata_path, {**identity, 'validator': current_validator})
                        with os.fdopen(descriptor, 'wb', closefd=False) as output:
                            received = 0
                            while True:
                                if time.monotonic() - started > max_download_seconds:
                                    raise ArchiveError('Archive download exceeded time limit')
                                block = response.read1(min(CHUNK, expected - received + 1))
                                if not block:
                                    break
                                if len(block) > expected - received:
                                    raise ArchiveError('Response exceeds declared download size')
                                output.write(block)
                                received += len(block)
                            output.flush()
                            os.fsync(output.fileno())
                        if received != expected:
                            raise ArchiveError('Interrupted or truncated archive download; partial retained')
                    finally:
                        os.close(descriptor)
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError) as exc:
                raise ArchiveError('Archive download interrupted; partial retained when available') from exc
            verify(manifest_path, partial, max_bytes=max_bytes, allow_http_for_tests=allow_http_for_tests)
            _publish_temporary(partial, destination)
            partial.unlink()
            metadata_path.unlink()
            return destination
        finally:
            os.close(lock)
