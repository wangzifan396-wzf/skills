from __future__ import annotations

import argparse
import sys
from pathlib import Path

from publisher_lib import (
    PublisherError,
    copy_assets,
    create_and_push_tag,
    create_github_release,
    create_source_archive,
    detect_version,
    ensure_remote,
    git,
    inspect_project,
    json_dump,
    normalize_version,
    now_iso,
    parse_github_slug,
    previous_tag,
    push_branch,
    release_notes,
    remote_inspect,
    require_fast_forward,
    require_git_project,
    sha256_file,
    verify_github_release,
    verify_remote,
    write_checksums,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Publish a Git project to GitHub and optionally create a verified Release"
    )
    result.add_argument("--project", required=True, help="Git project root")
    result.add_argument("--remote", required=True, help="GitHub HTTPS/SSH URL")
    result.add_argument("--confirm-repository", required=True, help="Retype OWNER/REPOSITORY")
    result.add_argument("--branch", default="main")
    result.add_argument("--remote-name", default="origin")
    result.add_argument("--commit-message", default="chore: publish project")
    result.add_argument("--version", help="Release version, such as 1.2.3")
    result.add_argument("--release", action="store_true", help="Create a GitHub Release after pushing")
    result.add_argument("--release-title", help="Release title")
    result.add_argument("--release-notes-file", help="Use an existing release notes file")
    result.add_argument("--asset", action="append", default=[], help="Release asset path; repeatable")
    result.add_argument("--artifact-dir", help="Directory outside the project for generated release assets")
    result.add_argument("--allow-existing", action="store_true", help="Allow same-history fast-forward updates")
    result.add_argument("--allow-local-remote", action="store_true", help="Allow file:// remotes for local testing")
    result.add_argument("--execute", action="store_true", help="Commit, push, tag, and create Release")
    result.add_argument("--receipt", default="github-project-publisher-receipt.json")
    return result


def staged_changes(project: Path) -> bool:
    return git(project, "diff", "--cached", "--quiet", check=False).returncode != 0


def prepare_artifacts(
    project: Path,
    artifact_dir: Path,
    tag: str,
    assets: list[str],
    notes: str,
) -> tuple[list[Path], Path]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    notes_file = artifact_dir / "RELEASE_NOTES.md"
    notes_file.write_text(notes, encoding="utf-8")
    archive = create_source_archive(project, artifact_dir, tag)
    copied = copy_assets(project, artifact_dir, assets)
    generated = [archive, *copied]
    checksums = write_checksums(generated, artifact_dir)
    return [*generated, checksums], notes_file


def main() -> int:
    args = parser().parse_args()
    receipt_path = Path(args.receipt).expanduser().resolve()
    started = now_iso()
    try:
        project = require_git_project(args.project)
        slug = parse_github_slug(args.remote)
        if slug is None and not args.allow_local_remote:
            raise PublisherError("--remote must be a GitHub HTTPS/SSH URL; use --allow-local-remote only for tests")
        if slug is not None and args.confirm_repository != slug:
            raise PublisherError(
                f"--confirm-repository must exactly match the remote: expected {slug}, got {args.confirm_repository}"
            )
        if args.release and slug is None:
            raise PublisherError("GitHub Release creation requires a GitHub remote, not a local file remote")

        audit = inspect_project(project)
        if audit["blockers"]:
            raise PublisherError("Publication blocked by local audit findings")
        version, version_source = detect_version(project, args.version)
        if args.release and version is None:
            raise PublisherError("--release requires --version or a version in package.json/pyproject.toml/Cargo.toml")
        tag = normalize_version(version) if version else None
        remote_audit = remote_inspect(args.remote, args.branch)
        if not remote_audit["empty"] and not args.allow_existing:
            raise PublisherError("Remote branch is non-empty; pass --allow-existing only after confirming same history")
        remote_action = ensure_remote(project, args.remote_name, args.remote, args.execute)

        notes = None
        artifact_dir = None
        artifacts: list[Path] = []
        notes_file = None
        release_plan = None
        if args.release:
            previous = previous_tag(project, tag)
            if args.release_notes_file:
                notes_file = Path(args.release_notes_file).expanduser().resolve()
                if not notes_file.is_file():
                    raise PublisherError(f"Release notes file does not exist: {notes_file}")
                notes = notes_file.read_text(encoding="utf-8")
            else:
                notes = release_notes(project, tag, args.release_title, previous)
            artifact_dir = Path(args.artifact_dir).expanduser().resolve() if args.artifact_dir else project.parent / f"{project.name}-{tag}-release"
            release_plan = {
                "tag": tag,
                "versionSource": version_source,
                "artifactDir": str(artifact_dir),
                "assetInputs": args.asset,
                "previousTag": previous,
                "notesPreview": notes[:2000],
            }

        receipt = {
            "schemaVersion": 1,
            "status": "planned",
            "mode": "execute" if args.execute else "dry-run",
            "startedAt": started,
            "completedAt": None,
            "project": str(project),
            "remote": args.remote,
            "repository": slug or args.confirm_repository,
            "branch": args.branch,
            "remoteName": args.remote_name,
            "commitMessage": args.commit_message,
            "version": tag,
            "audit": audit,
            "remoteAudit": remote_audit,
            "remoteAction": remote_action,
            "releasePlan": release_plan,
            "operations": [
                "stage approved project candidates",
                "git diff --cached --check",
                f'git commit -m "{args.commit_message}" when staged changes exist',
                f"fetch and require {args.branch} to be an ancestor of local HEAD when remote is non-empty",
                f"git push --set-upstream {args.remote_name} HEAD:refs/heads/{args.branch}",
            ],
            "verification": None,
        }
        if args.release:
            receipt["operations"].extend([
                f"create annotated tag {tag}",
                f"push refs/tags/{tag}",
                "create GitHub Release with source archive, SHA256SUMS, and requested assets",
                "verify remote branch, tag, and Release assets",
            ])

        if not args.execute:
            receipt["completedAt"] = now_iso()
            json_dump(receipt_path, receipt)
            print_json(receipt)
            return 0

        ensure_remote(project, args.remote_name, args.remote, True)
        require_fast_forward(project, args.remote_name, args.branch, remote_audit, args.allow_existing)
        git(project, "add", "-A")
        check = git(project, "diff", "--cached", "--check", check=False)
        if check.returncode != 0:
            raise PublisherError(f"Staged diff has whitespace errors:\n{check.stdout}{check.stderr}")
        if staged_changes(project):
            git(project, "commit", "-m", args.commit_message)
        push_branch(project, args.remote_name, args.branch)

        if args.release:
            assert tag is not None and notes is not None and artifact_dir is not None
            create_and_push_tag(project, args.remote_name, args.remote, tag, True)
            if args.release_notes_file:
                release_notes_path = notes_file
            else:
                artifact_dir.mkdir(parents=True, exist_ok=True)
                release_notes_path = artifact_dir / "RELEASE_NOTES.md"
                release_notes_path.write_text(notes, encoding="utf-8")
            artifacts, generated_notes = prepare_artifacts(project, artifact_dir, tag, args.asset, notes)
            release_notes_path = generated_notes if not args.release_notes_file else release_notes_path
            release = create_github_release(
                slug or args.confirm_repository,
                tag,
                args.release_title or f"Release {tag}",
                release_notes_path,
                artifacts,
                True,
            )
            release_verification = verify_github_release(
                slug or args.confirm_repository,
                tag,
                artifacts,
            )
            if not release_verification["assetsMatch"]:
                raise PublisherError("GitHub Release exists but one or more expected assets are missing")
            receipt["release"] = {
                "tag": tag,
                "notesFile": str(release_notes_path),
                "artifacts": [
                    {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
                    for path in artifacts
                ],
                "result": release,
                "verification": release_verification,
            }

        receipt["verification"] = verify_remote(project, args.remote, args.branch, tag)
        if not receipt["verification"]["verified"]:
            raise PublisherError("Publish completed but independent remote verification did not match")
        receipt["status"] = "published"
        receipt["completedAt"] = now_iso()
        json_dump(receipt_path, receipt)
        print_json(receipt)
        return 0
    except PublisherError as error:
        failure = {
            "schemaVersion": 1,
            "status": "blocked",
            "mode": "execute" if args.execute else "dry-run",
            "startedAt": started,
            "completedAt": now_iso(),
            "error": str(error),
        }
        json_dump(receipt_path, failure)
        print_json(failure, error=True)
        return 2


def print_json(payload: dict, error: bool = False) -> None:
    import json

    stream = sys.stderr if error else sys.stdout
    print(json.dumps(payload, indent=2, ensure_ascii=False), file=stream)


if __name__ == "__main__":
    raise SystemExit(main())
