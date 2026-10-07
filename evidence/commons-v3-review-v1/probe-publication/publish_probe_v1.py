#!/usr/bin/env python3
"""Package and publicly restore the completed temptation probe, without simulation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from swarm_societies import evidence_archive_v1 as archive

IDENTITY = "commons-v3-temptation-review-v1"
TAG = "commons-v3-temptation-review-2026-10-07"
REPO = "ReloadLightly/swarm-societies"
RELEASE = f"https://github.com/{REPO}/releases/tag/{TAG}"
BANK = ROOT / "evidence" / IDENTITY
ARTIFACTS = ROOT / "artifacts" / IDENTITY
RECEIPTS = Path(__file__).resolve().parent
WORK = ROOT / "runs/commons-v3-review-v1/probe-publication"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    data = value if isinstance(value, bytes) else (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f"preserved output differs: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def command(args):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True).stdout


def assets():
    return {IDENTITY + ".tar.gz": WORK / (IDENTITY + ".tar.gz"),
            IDENTITY + ".json": ARTIFACTS / (IDENTITY + ".json"),
            IDENTITY + "-catalog.json": WORK / (IDENTITY + "-catalog.json")}


def package():
    completion = read(BANK / "manifest.json")
    replay = read(BANK / "replay-receipt.json")
    if replay["episodes_exactly_replayed"] != 64 or replay["manifest_sha256"] != sha(BANK / "manifest.json"):
        raise ValueError("missing bound exact replay receipt")
    rows = []
    for name, pin in completion["files"].items():
        path = BANK / name
        if sha(path) != pin["sha256"] or path.stat().st_size != pin["bytes"]:
            raise ValueError(f"completed probe changed: {name}")
        if name.startswith("cases/"):
            rows.append({"path": str(path.relative_to(ROOT)), "sha256": pin["sha256"], "size": pin["bytes"]})
    rows.sort(key=lambda row: row["path"])
    if len(rows) != 64 or len(list((BANK / "cases").glob("*.json.gz"))) != 64:
        raise ValueError("expected exactly 64 recorded episodes")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    save(ARTIFACTS / "inventory.json", {"version": archive.INVENTORY_VERSION, "files": rows})
    manifest = archive.package(ROOT, ARTIFACTS / "inventory.json", assets()[IDENTITY + ".tar.gz"],
        ARTIFACTS / (IDENTITY + ".json"),
        source_url=f"https://github.com/{REPO}/releases/download/{TAG}/{IDENTITY}.tar.gz")
    result = archive.verify(ARTIFACTS / (IDENTITY + ".json"), assets()[IDENTITY + ".tar.gz"])
    result.update({"completion_manifest_sha256": sha(BANK / "manifest.json"),
                   "replay_receipt_sha256": sha(BANK / "replay-receipt.json"),
                   "publication_script_sha256": sha(Path(__file__)), "simulation_executed": False})
    save(RECEIPTS / "local-archive-verification.json", result)
    return result


def bind(source_commit):
    if len(source_commit) != 40:
        raise ValueError("full source commit required")
    names = ["design.json", "sources.json", "summary.json", "manifest.json", "original-stdout.txt", "replay-receipt.json"]
    names = [str((BANK / name).relative_to(ROOT)) for name in names]
    names += ["scripts/v3_temptation_probe.py", "scripts/capture_v3_temptation_probe_v1.py"]
    for name in names:
        committed = subprocess.run(["git", "show", source_commit + ":" + name], cwd=ROOT, capture_output=True, check=True).stdout
        if committed != (ROOT / name).read_bytes():
            raise ValueError(f"source commit does not bind {name}")
    manifest_path = ARTIFACTS / (IDENTITY + ".json")
    manifest = read(manifest_path)
    catalog = {"version": "evidence-catalog-v1", "release_url": RELEASE,
        "payload": "Only the 64 complete raw temptation-review episodes; compact evidence, sources, exact stdout and figures remain in Git.",
        "packager_runtime": {"python": platform.python_version(), "zlib": zlib.ZLIB_VERSION},
        "packager_source_sha256": sha(ROOT / "swarm_societies/evidence_archive_v1.py"),
        "studies": [{"id": IDENTITY, "manifest": manifest_path.name, "manifest_sha256": sha(manifest_path),
            "files": len(manifest["files"]), "file_bytes": manifest["total_file_bytes"], "archive_bytes": manifest["archive"]["size"],
            "source_provenance": {"bank": str(BANK.relative_to(ROOT)), "source_commit": source_commit,
                "completion_manifest_sha256": sha(BANK / "manifest.json"),
                "design_sha256": sha(BANK / "design.json"), "sources_manifest_sha256": sha(BANK / "sources.json"),
                "summary_sha256": sha(BANK / "summary.json"), "replay_receipt_sha256": sha(BANK / "replay-receipt.json")}}]}
    save(ARTIFACTS / "catalog.json", catalog)
    save(assets()[IDENTITY + "-catalog.json"], (ARTIFACTS / "catalog.json").read_bytes())
    result = {"source_commit": source_commit, "bound_committed_files": names,
              "asset_sha256": {name: sha(path) for name, path in assets().items()},
              "publication_script_sha256": sha(Path(__file__))}
    save(RECEIPTS / "source-commit-binding.json", result)
    return result


def public(url):
    request = urllib.request.Request(url, headers={"User-Agent": "swarm-temptation-publication-v1", "Cache-Control": "no-cache"})
    assert not request.has_header("Authorization")
    return urllib.request.urlopen(request, timeout=60)


def release():
    with public(f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}") as stream:
        return json.load(stream)


def check_assets():
    binding = read(RECEIPTS / "source-commit-binding.json")
    if sha(Path(__file__)) != binding["publication_script_sha256"]:
        raise ValueError("publication script changed")
    for name, path in assets().items():
        if sha(path) != binding["asset_sha256"][name]:
            raise ValueError("bound upload asset changed")
    return binding


def upload():
    binding = check_assets()
    try:
        release()
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    else:
        raise ValueError("release identity already exists; never replace or extend it")
    notes = WORK / "release-notes.md"
    save(notes, b"Exact reproduction of the user-supplied 7 October 2026 temptation probe.\n\n64 audited-policy episodes, eight disjoint review seeds, no model calls or evolutionary runs. All raw episodes replay exactly. Findings and ordinary descriptive intervals include the unresolved capacity-8/aggressive-peer endpoint. Source and per-file hashes are pinned; GitHub hosting is not administratively immutable.\n")
    stdout = command(["gh", "release", "create", TAG, "--repo", REPO, "--target", binding["source_commit"],
                      "--title", "Commons v3 temptation review: original probe evidence", "--notes-file", str(notes),
                      *map(str, assets().values())])
    result = {"release_url": RELEASE, "source_commit": binding["source_commit"],
              "new_release_only": True, "stdout": stdout.strip()}
    save(RECEIPTS / "upload.json", result)
    return result


def verify():
    binding = check_assets()
    remote = release()
    if remote["draft"] or remote["target_commitish"] != binding["source_commit"]:
        raise ValueError("public release target differs")
    attempt = Path(tempfile.mkdtemp(prefix="public-verify-", dir=WORK))
    downloads, restored, cache, offline = [attempt / name for name in ("downloads", "restored", "cache", "offline")]
    for path in (downloads, restored, cache, offline):
        path.mkdir()
    remote_assets = {row["name"]: row for row in remote["assets"]}
    if set(remote_assets) != set(assets()):
        raise ValueError("public release asset inventory differs")
    downloaded = []
    for name, original in assets().items():
        row = remote_assets[name]
        with public(row["browser_download_url"]) as response:
            data = response.read(row["size"] + 1)
        if len(data) != row["size"] or data != original.read_bytes():
            raise ValueError("public asset differs: " + name)
        save(downloads / name, data)
        downloaded.append({"id": row["id"], "name": name, "size": len(data), "sha256": sha(downloads / name),
                           "browser_download_url": row["browser_download_url"], "byte_identical": True})
    save(RECEIPTS / "public-assets.json", {"authenticated_download": False, "release_id": remote["id"], "assets": downloaded})
    base = [sys.executable, "scripts/restore_evidence_v1.py", "--catalog", str(downloads / (IDENTITY + "-catalog.json")),
            "--study", IDENTITY, "--cache", str(cache)]
    command([*base, "--root", str(restored), "--receipt", str(RECEIPTS / "public-restoration.json")])
    command([*base, "--root", str(restored), "--offline", "--verify-only", "--receipt", str(RECEIPTS / "offline-verification.json")])
    command([*base, "--root", str(offline), "--offline", "--receipt", str(RECEIPTS / "offline-restoration.json")])
    manifest = read(ARTIFACTS / (IDENTITY + ".json"))
    comparisons = []
    for row in manifest["files"]:
        original = ROOT / row["path"]
        for root in (restored, offline):
            path = root / row["path"]
            if path.read_bytes() != original.read_bytes() or sha(path) != row["sha256"] or path.stat().st_size != row["size"]:
                raise ValueError("restored file differs: " + row["path"])
        comparisons.append({**row, "public_restoration_byte_identical": True, "offline_restoration_byte_identical": True})
    save(RECEIPTS / "restored-byte-comparison.json", {"files": len(comparisons), "payload": comparisons})
    result = {"version": "commons-v3-temptation-publication-v1", "status": "ok", "release_url": RELEASE,
              "release_id": remote["id"], "release_immutable": remote.get("immutable", False),
              "published_at": remote["published_at"], "release_target_commit": remote["target_commitish"],
              "authenticated_download": False, "initial_cache_empty": True, "initial_restore_roots_empty": True,
              "public_restored_files": len(comparisons), "public_restored_bytes": manifest["total_file_bytes"],
              "archive_bytes": manifest["archive"]["size"], "archive_sha256": manifest["archive"]["sha256"],
              "all_public_assets_byte_identical": True, "all_public_and_offline_restored_files_byte_identical": True,
              "offline_archive_verification_passed": True, "simulation_executed": False}
    save(RECEIPTS / "publication.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("package", "bind", "upload", "verify"))
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    if args.command == "bind" and not args.source_commit:
        parser.error("bind requires --source-commit")
    result = bind(args.source_commit) if args.command == "bind" else {"package": package, "upload": upload, "verify": verify}[args.command]()
    print(json.dumps(result, indent=2, sort_keys=True))
