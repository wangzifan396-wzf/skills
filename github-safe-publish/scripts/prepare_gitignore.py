from __future__ import annotations

import argparse
import json
from pathlib import Path

from inspect_project import observed_ignore_suggestions
from publish_lib import PublishError


BLOCK_HEADER = "# github-safe-publish: local and generated files"


def existing_rules(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def ordered_patterns(items: list[dict[str, str]]) -> list[dict[str, str]]:
    env_order = {".env": 0, ".env.*": 1, "!.env.example": 2, "!.env.sample": 3}
    return sorted(items, key=lambda item: (0, env_order[item["pattern"]]) if item["pattern"] in env_order else (1, item["pattern"]))


def plan(project: Path) -> dict:
    root = project.expanduser().resolve()
    if not root.is_dir():
        raise PublishError(f"Project directory does not exist: {root}")
    target = root / ".gitignore"
    current = existing_rules(target)
    observed = ordered_patterns(observed_ignore_suggestions(root))
    additions = [item for item in observed if item["pattern"] not in current]
    return {
        "schemaVersion": 1,
        "project": str(root),
        "gitignore": str(target),
        "present": target.is_file(),
        "additions": additions,
        "changed": bool(additions),
    }


def apply_plan(payload: dict) -> None:
    if not payload["additions"]:
        return
    target = Path(payload["gitignore"])
    original = target.read_text(encoding="utf-8", errors="replace") if target.is_file() else ""
    prefix = original
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    if prefix and not prefix.endswith("\n\n"):
        prefix += "\n"
    block = [BLOCK_HEADER, *(item["pattern"] for item in payload["additions"]), ""]
    target.write_text(prefix + "\n".join(block), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview conservative .gitignore additions")
    parser.add_argument("project", type=Path, help="Project root")
    parser.add_argument("--write", action="store_true", help="Append the reviewed additions")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = plan(args.project)
        if args.write:
            apply_plan(payload)
            payload["written"] = payload["changed"]
        else:
            payload["written"] = False
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except PublishError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
