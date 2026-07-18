from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit


GITHUB_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]+$")


class PublishError(RuntimeError):
    """A safe, user-facing publication error."""


class CommandError(PublishError):
    def __init__(self, command: Sequence[str], returncode: int, stderr: str):
        self.command = list(command)
        self.returncode = returncode
        self.stderr = stderr.strip()
        super().__init__(self.stderr or f"Command exited with code {returncode}")


@dataclass(frozen=True)
class GitHubRemote:
    original: str
    owner: str
    repository: str
    transport: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repository}"

    @property
    def canonical_url(self) -> str:
        return f"https://github.com/{self.slug}"

    @property
    def git_url(self) -> str:
        return f"{self.canonical_url}.git"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_github_remote(value: str) -> GitHubRemote:
    raw = value.strip()
    if not raw or "\n" in raw or "\r" in raw:
        raise PublishError("A single GitHub repository URL is required")

    owner: str
    repository: str
    transport: str

    scp_match = re.fullmatch(r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?", raw, re.IGNORECASE)
    if scp_match:
        owner, repository = scp_match.groups()
        transport = "ssh"
    else:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"https", "ssh"} or host != "github.com":
            raise PublishError("Only HTTPS or SSH github.com repository URLs are supported")
        if parsed.query or parsed.fragment:
            raise PublishError("Repository URLs must not contain query strings or fragments")
        if parsed.scheme == "https" and (parsed.username or parsed.password):
            raise PublishError("Do not embed credentials in a GitHub URL")
        if parsed.scheme == "ssh" and parsed.username not in {None, "git"}:
            raise PublishError("GitHub SSH URLs may only use the git user")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2:
            raise PublishError("Use a repository URL such as https://github.com/OWNER/REPOSITORY")
        owner, repository = parts
        transport = parsed.scheme

    if repository.lower().endswith(".git"):
        repository = repository[:-4]
    if not owner or not repository:
        raise PublishError("The GitHub URL must contain an owner and repository")
    if not GITHUB_COMPONENT.fullmatch(owner) or not GITHUB_COMPONENT.fullmatch(repository):
        raise PublishError("The GitHub owner or repository contains unsupported characters")
    if owner in {".", ".."} or repository in {".", ".."}:
        raise PublishError("Invalid GitHub repository path")

    return GitHubRemote(raw, owner, repository, transport)


def safe_remote_dict(remote: GitHubRemote) -> dict[str, str]:
    return {
        "owner": remote.owner,
        "repository": remote.repository,
        "slug": remote.slug,
        "canonicalUrl": remote.canonical_url,
        "transport": remote.transport,
    }


def run_command(
    command: Sequence[str],
    *,
    cwd: Path | str | None = None,
    check: bool = True,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    process = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and process.returncode:
        stderr = process.stderr.decode("utf-8", errors="replace")
        raise CommandError(command, process.returncode, stderr)
    return process


def run_git(
    args: Sequence[str],
    *,
    cwd: Path | str | None = None,
    check: bool = True,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return run_command(["git", *args], cwd=cwd, check=check, input_bytes=input_bytes)


def decoded(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").strip()


def git_is_repository(project: Path) -> bool:
    result = run_git(["rev-parse", "--is-inside-work-tree"], cwd=project, check=False)
    return result.returncode == 0 and decoded(result.stdout) == "true"


def git_root(project: Path) -> Path | None:
    if not git_is_repository(project):
        return None
    result = run_git(["rev-parse", "--show-toplevel"], cwd=project)
    return Path(decoded(result.stdout)).resolve()


def git_has_head(project: Path) -> bool:
    return run_git(["rev-parse", "--verify", "HEAD"], cwd=project, check=False).returncode == 0


def git_text(args: Sequence[str], *, cwd: Path, check: bool = True) -> str:
    return decoded(run_git(args, cwd=cwd, check=check).stdout)


def git_lines(args: Sequence[str], *, cwd: Path, check: bool = True) -> list[str]:
    value = git_text(args, cwd=cwd, check=check)
    return value.splitlines() if value else []


def inspect_remote(remote: GitHubRemote) -> dict[str, Any]:
    head_result = run_git(["ls-remote", "--symref", remote.original, "HEAD"], check=False)
    if head_result.returncode:
        error = decoded(head_result.stderr)
        error = error.replace(remote.original, remote.canonical_url)
        return {
            "schemaVersion": 1,
            "checkedAt": utc_now(),
            "remote": safe_remote_dict(remote),
            "accessible": False,
            "empty": None,
            "defaultBranch": None,
            "heads": [],
            "error": error or "git ls-remote failed",
        }

    default_branch = None
    for line in decoded(head_result.stdout).splitlines():
        match = re.match(r"ref:\s+refs/heads/(\S+)\s+HEAD$", line)
        if match:
            default_branch = match.group(1)

    heads_result = run_git(["ls-remote", "--heads", remote.original], check=False)
    if heads_result.returncode:
        error = decoded(heads_result.stderr).replace(remote.original, remote.canonical_url)
        return {
            "schemaVersion": 1,
            "checkedAt": utc_now(),
            "remote": safe_remote_dict(remote),
            "accessible": False,
            "empty": None,
            "defaultBranch": default_branch,
            "heads": [],
            "error": error or "Unable to inspect remote branches",
        }

    heads: list[dict[str, str]] = []
    for line in decoded(heads_result.stdout).splitlines():
        if not line:
            continue
        sha, ref = line.split("\t", 1)
        heads.append({"branch": ref.removeprefix("refs/heads/"), "sha": sha})

    return {
        "schemaVersion": 1,
        "checkedAt": utc_now(),
        "remote": safe_remote_dict(remote),
        "accessible": True,
        "empty": not heads,
        "defaultBranch": default_branch,
        "heads": heads,
        "error": None,
    }


def write_json(path: Path | str | None, payload: Any) -> None:
    if path is None:
        return
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def null_split(data: bytes) -> list[str]:
    return [item.decode("utf-8", errors="surrogateescape") for item in data.split(b"\0") if item]


def chunks(values: Sequence[str], size: int = 100) -> Iterable[Sequence[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def remote_asdict(remote: GitHubRemote) -> dict[str, Any]:
    payload = asdict(remote)
    payload.pop("original", None)
    payload["slug"] = remote.slug
    payload["canonical_url"] = remote.canonical_url
    return payload
