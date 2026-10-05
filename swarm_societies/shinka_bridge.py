"""Subscription-only transport for ShinkaEvolve's native Headless provider.

The evolutionary algorithm, mutation parsing, archive, sampling and database are
the unmodified upstream ShinkaEvolve engine. This module only translates its
documented Headless command protocol into Codex CLI JSONL.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


MODEL = "gpt-6-astra"
EFFORT = "xhigh"
SERVICE_TIER = "fast"
UPSTREAM_REVISION = "9912af12d423504b8d580f4179fd15f5f88b8c50"


def subscription_environment() -> dict[str, str]:
    """Remove provider keys; never synthesize or copy credentials."""
    return {
        key: value for key, value in os.environ.items()
        if not key.endswith("API_KEY")
        and key not in {"OPENAI_BASE_URL", "OPENAI_API_BASE", "ANTHROPIC_AUTH_TOKEN"}
    }


def check_subscription() -> dict:
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("codex executable is unavailable")
    env = subscription_environment()
    status = subprocess.run(
        [executable, "login", "status"], text=True, capture_output=True,
        timeout=30, env=env, check=False,
    )
    detail = (status.stdout + status.stderr).strip()
    if status.returncode or "Logged in using ChatGPT" not in detail:
        raise RuntimeError(f"ChatGPT subscription authentication required: {detail}")
    auth_path = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
    if auth_path.exists():
        auth = json.loads(auth_path.read_text())
        if auth.get("auth_mode") != "chatgpt" or auth.get("OPENAI_API_KEY"):
            raise RuntimeError("Refusing non-ChatGPT or mixed API-key authentication")
    version = subprocess.run(
        [executable, "--version"], text=True, capture_output=True,
        timeout=15, env=env, check=True,
    ).stdout.strip()
    return {"executable": executable, "version": version,
            "authentication": "chatgpt", "model": MODEL,
            "reasoning_effort": EFFORT, "service_tier": SERVICE_TIER,
            "paid_api_keys_removed": True}


def parse_codex_events(stdout: str) -> tuple[str, dict]:
    messages = []
    usage = None
    errors = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message":
                messages.append(item.get("text", ""))
        elif event.get("type") == "turn.completed":
            usage = event.get("usage", {})
        elif event.get("type") in {"error", "turn.failed"}:
            errors.append(event)
    if usage is None or not messages:
        raise RuntimeError(f"No completed Codex response; errors={errors}")
    return messages[-1], {
        **usage,
        "thinking_tokens": usage.get("reasoning_output_tokens", 0),
        "usage_status": "reported_by_codex_cli",
        "pricing_status": "subscription_no_per_call_price",
        "cost_basis": "subscription",
        "num_total_queries": 1,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent", nargs="?", default="codex")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--work-dir", type=Path, default=Path.cwd())
    parser.add_argument("--allow", default="read-only")
    parser.add_argument("--usage", action="store_true")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--reasoning-effort", default=EFFORT)
    args = parser.parse_args(argv)
    try:
        settings = check_subscription()
        if args.check:
            print(json.dumps(settings))
            return 0
        if (args.agent, args.model, args.reasoning_effort, args.allow) != (
            "codex", MODEL, EFFORT, "read-only"
        ):
            raise RuntimeError("Requested route differs from the verified subscription settings")
        if not args.prompt_file:
            raise RuntimeError("--prompt-file is required")
        prompt = args.prompt_file.read_text()
        evidence = args.work_dir / "subscription_calls"
        evidence.mkdir(parents=True, exist_ok=True)
        call_id = args.prompt_file.stem
        start = time.monotonic()
        # Candidate inference receives its prompt in an empty working directory.
        # It has no reason to inspect the protected evaluator or holdout seeds.
        with tempfile.TemporaryDirectory(prefix="swarm-proposal-") as isolated:
            command = [
                settings["executable"], "exec", "--ephemeral", "--ignore-user-config",
                "--ignore-rules", "--skip-git-repo-check", "--model", MODEL,
                "-c", f'model_reasoning_effort="{EFFORT}"',
                "-c", f'service_tier="{SERVICE_TIER}"',
                "-c", 'forced_login_method="chatgpt"',
                "-c", 'web_search="disabled"',
                "--disable", "shell_tool", "--disable", "unified_exec",
                "--disable", "apps", "--disable", "plugins",
                "--disable", "multi_agent", "--disable", "browser_use",
                "--disable", "in_app_browser", "--disable", "image_generation",
                "--disable", "view_image", "--enable", "skip_host_skill_discovery",
                "--sandbox", "read-only", "--json", "-C", isolated, "-",
            ]
            # Write traces live so a hard budget cutoff preserves partial events.
            stdout_path = evidence / f"{call_id}.jsonl"
            stderr_path = evidence / f"{call_id}.stderr"
            with stdout_path.open("w") as out, stderr_path.open("w") as err:
                process = subprocess.Popen(
                    command, stdin=subprocess.PIPE, stdout=out, stderr=err,
                    text=True, env=subscription_environment(),
                )
                try:
                    process.communicate(
                        "This is a pure program-mutation request. Do not call tools or inspect "
                        "files. Return the requested mutation using only the supplied prompt.\n\n" + prompt,
                        timeout=float(os.environ.get("SWARM_CODEX_TIMEOUT", "900")),
                    )
                except subprocess.TimeoutExpired:
                    # The codex launcher may have a native child process; killing
                    # just the Node launcher would leak an inference request.
                    import psutil
                    try:
                        for child in psutil.Process(process.pid).children(recursive=True):
                            try:
                                child.kill()
                            except psutil.Error:
                                pass
                    except psutil.Error:
                        pass
                    process.kill()
                    process.wait()
                    raise RuntimeError(f"Codex request timed out; partial evidence={stdout_path}")
            completed = subprocess.CompletedProcess(
                command, process.returncode, stdout_path.read_text(), stderr_path.read_text()
            )
        metadata = {**settings, "elapsed_seconds": time.monotonic() - start,
                    "returncode": completed.returncode, "prompt_path": str(args.prompt_file)}
        (evidence / f"{call_id}.metadata.json").write_text(json.dumps(metadata, indent=2))
        if completed.returncode:
            raise RuntimeError(
                f"Codex exit {completed.returncode}; evidence={evidence / call_id}; "
                f"stderr={completed.stderr[-4000:]} stdout={completed.stdout[-4000:]}"
            )
        content, usage = parse_codex_events(completed.stdout)
        print(content)
        print(json.dumps({"usage": usage}))
        return 0
    except Exception as exc:
        print(f"Subscription route failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
