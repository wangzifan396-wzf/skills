from __future__ import annotations

import argparse
import json
from pathlib import Path

from publish_lib import (
    CommandError,
    PublishError,
    decoded,
    git_has_head,
    git_is_repository,
    git_lines,
    git_text,
    parse_github_remote,
    run_git,
    safe_remote_dict,
    utc_now,
    write_json,
)


def verify(project: Path, remote_value: str, branch: str) -> dict:
    root = project.expanduser().resolve()
    if not root.is_dir():
        raise PublishError(f"Project directory does not exist: {root}")
    if not git_is_repository(root) or not git_has_head(root):
        raise PublishError("The project must be a Git repository with a local HEAD")

    remote = parse_github_remote(remote_value)
    local_sha = git_text(["rev-parse", "HEAD"], cwd=root)
    result = run_git(["ls-remote", remote.original, f"refs/heads/{branch}"], check=False)
    if result.returncode:
        raise CommandError(
            ["git", "ls-remote", remote.canonical_url, f"refs/heads/{branch}"],
            result.returncode,
            decoded(result.stderr).replace(remote.original, remote.canonical_url),
        )
    output = decoded(result.stdout)
    remote_sha = output.split("\t", 1)[0] if output else None
    status = git_lines(["status", "--short", "--branch"], cwd=root)
    dirty_entries = [line for line in status if not line.startswith("##")]

    return {
        "schemaVersion": 1,
        "verifiedAt": utc_now(),
        "project": str(root),
        "remote": safe_remote_dict(remote),
        "branch": branch,
        "localHead": local_sha,
        "remoteHead": remote_sha,
        "headMatches": local_sha == remote_sha,
        "worktreeClean": not dirty_entries,
        "status": status,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare a local Git HEAD with a GitHub branch")
    parser.add_argument("--project", required=True, type=Path, help="Project root")
    parser.add_argument("--remote", required=True, help="HTTPS or SSH GitHub repository URL")
    parser.add_argument("--branch", default="main", help="Remote branch (default: main)")
    parser.add_argument("--json-out", type=Path, help="Write verification JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = verify(args.project, args.remote, args.branch)
        write_json(args.json_out, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["headMatches"] else 3
    except (PublishError, CommandError) as exc:
        payload = {"schemaVersion": 1, "status": "failed", "error": str(exc)}
        write_json(args.json_out, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
