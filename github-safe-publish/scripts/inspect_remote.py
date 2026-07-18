from __future__ import annotations

import argparse
import json
from pathlib import Path

from publish_lib import PublishError, inspect_remote, parse_github_remote, print_json, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a GitHub repository without modifying it")
    parser.add_argument("remote", help="HTTPS or SSH GitHub repository URL")
    parser.add_argument("--json-out", type=Path, help="Write the remote inspection as JSON")
    parser.add_argument("--require-empty", action="store_true", help="Exit with code 3 when the remote has branches")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        remote = parse_github_remote(args.remote)
        payload = inspect_remote(remote)
    except PublishError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    write_json(args.json_out, payload)
    print_json(payload)
    if not payload["accessible"]:
        return 2
    if args.require_empty and not payload["empty"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
