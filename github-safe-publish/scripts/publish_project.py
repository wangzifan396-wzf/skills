from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from inspect_project import build_manifest
from publish_lib import (
    CommandError,
    PublishError,
    chunks,
    decoded,
    git_has_head,
    git_is_repository,
    git_lines,
    git_text,
    inspect_remote,
    parse_github_remote,
    run_git,
    safe_remote_dict,
    utc_now,
    write_json,
)


BRANCH_PATTERN = re.compile(r"^(?!/)(?!.*(?:\.\.|//|@\{|\\|\s))(?!.*[/.]$)[A-Za-z0-9._/-]+$")
REMOTE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_confirmation(value: str, expected_slug: str) -> str:
    confirmation = value.strip().removesuffix(".git").strip("/")
    if confirmation.lower() != expected_slug.lower():
        raise PublishError(
            f"Repository confirmation '{confirmation}' does not match the parsed target '{expected_slug}'"
        )
    return confirmation


def validate_options(args: argparse.Namespace) -> None:
    if not BRANCH_PATTERN.fullmatch(args.branch):
        raise PublishError(f"Invalid target branch: {args.branch}")
    if not REMOTE_NAME_PATTERN.fullmatch(args.remote_name):
        raise PublishError(f"Invalid Git remote name: {args.remote_name}")
    if not args.commit_message.strip() or "\n" in args.commit_message or "\r" in args.commit_message:
        raise PublishError("Commit message must be a non-empty single line")
    if len(args.commit_message) > 200:
        raise PublishError("Commit message must not exceed 200 characters")


def existing_remote_url(project: Path, name: str) -> str | None:
    if not git_is_repository(project):
        return None
    result = run_git(["remote", "get-url", name], cwd=project, check=False)
    return decoded(result.stdout) if result.returncode == 0 else None


def matching_remote(project: Path, name: str, expected_slug: str) -> tuple[bool, str | None]:
    value = existing_remote_url(project, name)
    if value is None:
        return False, None
    try:
        parsed = parse_github_remote(value)
    except PublishError:
        return False, value
    return parsed.slug.lower() == expected_slug.lower(), value


def plan_publication(args: argparse.Namespace) -> dict[str, Any]:
    validate_options(args)
    project = args.project.expanduser().resolve()
    if not project.is_dir():
        raise PublishError(f"Project directory does not exist: {project}")

    remote = parse_github_remote(args.remote)
    validate_confirmation(args.confirm_repository, remote.slug)
    manifest = build_manifest(project)
    remote_state = inspect_remote(remote)
    blockers = [dict(item) for item in manifest["findings"] if item["severity"] == "blocker"]
    warnings = [dict(item) for item in manifest["findings"] if item["severity"] == "warning"]

    if not remote_state["accessible"]:
        blockers.append(
            {
                "severity": "blocker",
                "code": "remote-unavailable",
                "path": None,
                "message": remote_state["error"] or "The GitHub repository is not accessible",
            }
        )

    repo_exists = manifest["git"]["isRepository"]
    remote_matches, existing_url = matching_remote(project, args.remote_name, remote.slug)
    if existing_url is not None and not remote_matches:
        blockers.append(
            {
                "severity": "blocker",
                "code": "remote-name-conflict",
                "path": None,
                "message": (
                    f"Existing remote '{args.remote_name}' points somewhere else; preserve it and choose "
                    "an unused --remote-name"
                ),
            }
        )

    target_head = None
    if remote_state["accessible"] and not remote_state["empty"]:
        for head in remote_state["heads"]:
            if head["branch"] == args.branch:
                target_head = head
                break
        if not args.allow_existing:
            blockers.append(
                {
                    "severity": "blocker",
                    "code": "remote-not-empty",
                    "path": None,
                    "message": "The remote has branches; first publication only supports an empty remote by default",
                }
            )
        elif not repo_exists or not manifest["git"]["hasHead"]:
            blockers.append(
                {
                    "severity": "blocker",
                    "code": "missing-local-history",
                    "path": None,
                    "message": "A non-empty remote can only be updated from an existing local Git history",
                }
            )
        elif not remote_matches:
            blockers.append(
                {
                    "severity": "blocker",
                    "code": "unbound-existing-remote",
                    "path": None,
                    "message": "Bind and review the same-history remote before enabling --allow-existing",
                }
            )
        elif target_head is None:
            blockers.append(
                {
                    "severity": "blocker",
                    "code": "target-branch-missing",
                    "path": None,
                    "message": f"The non-empty remote does not advertise refs/heads/{args.branch}",
                }
            )

    operations: list[str] = []
    if not repo_exists:
        operations.append(f"git init --initial-branch={args.branch}")
    operations.extend(
        [
            "stage tracked updates/deletions and scanner-approved candidate files",
            "git diff --cached --check",
            f"git commit -m {json.dumps(args.commit_message)} when staged changes exist",
        ]
    )
    if existing_url is None:
        operations.append(f"git remote add {args.remote_name} {remote.canonical_url}.git")
    if args.allow_existing and not remote_state.get("empty"):
        operations.append(f"fetch and require refs/heads/{args.branch} to be an ancestor of local HEAD")
    operations.extend(
        [
            f"git push --set-upstream {args.remote_name} HEAD:refs/heads/{args.branch}",
            "compare local HEAD with the SHA advertised by the remote target branch",
        ]
    )

    return {
        "schemaVersion": 1,
        "plannedAt": utc_now(),
        "mode": "execute" if args.execute else "dry-run",
        "project": str(project),
        "remote": safe_remote_dict(remote),
        "branch": args.branch,
        "remoteName": args.remote_name,
        "commitMessage": args.commit_message,
        "allowExisting": args.allow_existing,
        "projectAudit": {
            "candidateFiles": manifest["summary"]["candidateFiles"],
            "candidateBytes": manifest["summary"]["candidateBytes"],
            "ignoredPathEntries": manifest["summary"]["ignoredPathEntries"],
            "blockers": manifest["summary"]["blockers"],
            "warnings": manifest["summary"]["warnings"],
            "readiness": manifest["readiness"],
            "git": manifest["git"],
        },
        "remoteAudit": remote_state,
        "blockers": blockers,
        "warnings": warnings,
        "operations": operations,
        "ready": not blockers,
        "candidatePaths": [item["path"] for item in manifest["candidateFiles"]],
    }


def ensure_same_history(project: Path, remote_name: str, branch: str) -> None:
    remote_ref = f"refs/remotes/{remote_name}/{branch}"
    fetch_refspec = f"refs/heads/{branch}:{remote_ref}"
    run_git(["fetch", "--no-tags", remote_name, fetch_refspec], cwd=project)
    ancestor = run_git(["merge-base", "--is-ancestor", remote_ref, "HEAD"], cwd=project, check=False)
    if ancestor.returncode != 0:
        raise PublishError(
            "The remote target branch is not an ancestor of local HEAD; refusing a non-fast-forward update"
        )


def stage_candidates(project: Path, candidates: list[str]) -> None:
    if git_has_head(project):
        run_git(["add", "-u"], cwd=project)
    for group in chunks(candidates, 80):
        run_git(["add", "--", *group], cwd=project)


def cached_changes_exist(project: Path) -> bool:
    result = run_git(["diff", "--cached", "--quiet", "--exit-code"], cwd=project, check=False)
    if result.returncode not in {0, 1}:
        raise CommandError(["git", "diff", "--cached", "--quiet", "--exit-code"], result.returncode, decoded(result.stderr))
    return result.returncode == 1


def remote_branch_sha(remote_value: str, branch: str) -> str | None:
    result = run_git(["ls-remote", remote_value, f"refs/heads/{branch}"], check=False)
    if result.returncode:
        raise CommandError(["git", "ls-remote", "<remote>", f"refs/heads/{branch}"], result.returncode, decoded(result.stderr))
    output = decoded(result.stdout)
    return output.split("\t", 1)[0] if output else None


def execute_publication(args: argparse.Namespace, plan: dict[str, Any]) -> dict[str, Any]:
    project = Path(plan["project"])
    remote = parse_github_remote(args.remote)
    started = utc_now()

    if not git_is_repository(project):
        run_git(["init", f"--initial-branch={args.branch}"], cwd=project)

    matches, current_remote_url = matching_remote(project, args.remote_name, remote.slug)
    if current_remote_url is not None and not matches:
        raise PublishError(f"Remote '{args.remote_name}' changed after dry-run; refusing to rewrite it")
    if current_remote_url is None:
        run_git(["remote", "add", args.remote_name, remote.original], cwd=project)
        current_remote_url = remote.original

    if args.allow_existing and not plan["remoteAudit"]["empty"]:
        if not git_has_head(project):
            raise PublishError("Local HEAD is required before updating a non-empty remote")
        ensure_same_history(project, args.remote_name, args.branch)

    stage_candidates(project, plan["candidatePaths"])
    whitespace = run_git(["diff", "--cached", "--check"], cwd=project, check=False)
    if whitespace.returncode:
        raise PublishError(decoded(whitespace.stdout or whitespace.stderr) or "git diff --cached --check failed")

    commit_created = False
    if cached_changes_exist(project):
        run_git(["commit", "-m", args.commit_message], cwd=project)
        commit_created = True
    elif not git_has_head(project):
        raise PublishError("No publishable files were staged, so an initial commit cannot be created")

    local_sha = git_text(["rev-parse", "HEAD"], cwd=project)
    run_git(
        [
            "push",
            "--set-upstream",
            args.remote_name,
            f"HEAD:refs/heads/{args.branch}",
        ],
        cwd=project,
    )
    observed_remote_sha = remote_branch_sha(current_remote_url, args.branch)
    verified = observed_remote_sha == local_sha
    if not verified:
        raise PublishError(
            f"Push returned, but remote refs/heads/{args.branch} does not match local HEAD"
        )
    post_publish_status = git_lines(["status", "--short", "--branch"], cwd=project)

    return {
        "schemaVersion": 1,
        "status": "published",
        "startedAt": started,
        "completedAt": utc_now(),
        "project": str(project),
        "remote": safe_remote_dict(remote),
        "branch": args.branch,
        "remoteName": args.remote_name,
        "commitCreated": commit_created,
        "localHead": local_sha,
        "remoteHead": observed_remote_sha,
        "verified": verified,
        "postPublishStatus": post_publish_status,
        "candidateFiles": plan["projectAudit"]["candidateFiles"],
        "ignoredPathEntries": plan["projectAudit"]["ignoredPathEntries"],
    }


def public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    payload = dict(plan)
    payload.pop("candidatePaths", None)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely publish a reviewed local project to GitHub")
    parser.add_argument("--project", required=True, type=Path, help="Project root")
    parser.add_argument("--remote", required=True, help="HTTPS or SSH GitHub repository URL")
    parser.add_argument("--confirm-repository", required=True, help="Retype OWNER/REPOSITORY")
    parser.add_argument("--branch", default="main", help="Target branch (default: main)")
    parser.add_argument("--remote-name", default="origin", help="Git remote name (default: origin)")
    parser.add_argument("--commit-message", default="chore: publish project", help="Single-line commit message")
    parser.add_argument("--allow-existing", action="store_true", help="Allow same-history fast-forward remote updates")
    parser.add_argument("--execute", action="store_true", help="Commit and push; omit for a mutation-free dry-run")
    parser.add_argument("--receipt", type=Path, help="Write the dry-run plan or final receipt as JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        plan = plan_publication(args)
        if not plan["ready"]:
            payload = public_plan(plan)
            write_json(args.receipt, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 2
        if not args.execute:
            payload = public_plan(plan)
            write_json(args.receipt, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        receipt = execute_publication(args, plan)
        write_json(args.receipt, receipt)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0
    except (PublishError, CommandError) as exc:
        payload = {
            "schemaVersion": 1,
            "status": "failed",
            "failedAt": utc_now(),
            "error": str(exc),
        }
        write_json(args.receipt, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
