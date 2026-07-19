from __future__ import annotations

import argparse
import sys
from pathlib import Path

from publisher_lib import PublisherError, json_dump, now_iso, parse_github_slug, require_git_project, verify_remote


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently verify a GitHub project publish")
    parser.add_argument("--project", required=True)
    parser.add_argument("--remote", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--tag")
    parser.add_argument("--allow-local-remote", action="store_true")
    parser.add_argument("--json-out", default="github-project-publisher-verification.json")
    args = parser.parse_args()
    try:
        project = require_git_project(args.project)
        if parse_github_slug(args.remote) is None and not args.allow_local_remote:
            raise PublisherError("--remote must be a GitHub URL")
        verification = verify_remote(project, args.remote, args.branch, args.tag)
        payload = {
            "schemaVersion": 1,
            "verifiedAt": now_iso(),
            "project": str(project),
            "remote": args.remote,
            "branch": args.branch,
            **verification,
        }
        json_dump(Path(args.json_out).expanduser().resolve(), payload)
        print_json(payload)
        return 0 if verification["verified"] else 2
    except PublisherError as error:
        print(json.dumps({"status": "blocked", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


def print_json(payload: dict) -> None:
    import json

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
