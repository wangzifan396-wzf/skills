from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "github-project-publisher" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from publisher_lib import (  # noqa: E402
    create_source_archive,
    detect_version,
    inspect_candidate,
    normalize_version,
    parse_github_slug,
    release_notes,
    sha256_file,
)


def run_git(project: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=project,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=check,
    )


class GithubProjectPublisherTests(unittest.TestCase):
    def test_github_slug_and_version_normalization(self) -> None:
        self.assertEqual(parse_github_slug("https://github.com/acme/demo.git"), "acme/demo")
        self.assertEqual(parse_github_slug("git@github.com:acme/demo"), "acme/demo")
        self.assertIsNone(parse_github_slug("https://gitlab.com/acme/demo"))
        self.assertEqual(normalize_version("1.2.3"), "v1.2.3")
        self.assertEqual(normalize_version("v2.0.0-rc.1"), "v2.0.0-rc.1")

    def test_secret_and_large_file_findings_are_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            private = project / "config.txt"
            private.write_text('api_' + 'key = "not-a-real-secret-value"\n', encoding="utf-8")
            findings = inspect_candidate(project, "config.txt")
            self.assertTrue(any(item.rule == "secret-assignment" for item in findings))
            self.assertNotIn("not-a-real-secret-value", " ".join(item.message for item in findings))

    def test_version_notes_and_source_archive_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "demo"
            project.mkdir()
            run_git(project, "init", "-b", "main")
            run_git(project, "config", "user.email", "test@example.invalid")
            run_git(project, "config", "user.name", "Publisher Test")
            (project / "README.md").write_text("demo\n", encoding="utf-8")
            (project / "package.json").write_text('{"name":"demo","version":"1.2.3"}\n', encoding="utf-8")
            run_git(project, "add", "-A")
            run_git(project, "commit", "-m", "feat: add demo")
            self.assertEqual(detect_version(project), ("v1.2.3", "package.json"))
            notes = release_notes(project, "v1.2.3")
            self.assertIn("feat: add demo", notes)
            output = Path(temporary) / "artifacts"
            archive = create_source_archive(project, output, "v1.2.3")
            self.assertTrue(archive.is_file())
            self.assertGreater(archive.stat().st_size, 0)
            self.assertEqual(len(sha256_file(archive)), 64)

    def test_execute_branch_publish_against_local_bare_remote(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "demo"
            project.mkdir()
            run_git(project, "init", "-b", "main")
            run_git(project, "config", "user.email", "test@example.invalid")
            run_git(project, "config", "user.name", "Publisher Test")
            (project / "README.md").write_text("demo\n", encoding="utf-8")
            run_git(project, "add", "-A")
            run_git(project, "commit", "-m", "chore: initial")
            remote = root / "remote.git"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)
            remote_url = remote.as_uri()
            run_git(project, "remote", "add", "origin", remote_url)
            (project / "CHANGELOG.md").write_text("first\n", encoding="utf-8")
            receipt = root / "receipt.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "publish_project.py"),
                    "--project",
                    str(project),
                    "--remote",
                    remote_url,
                    "--confirm-repository",
                    "local/test",
                    "--allow-local-remote",
                    "--execute",
                    "--receipt",
                    str(receipt),
                ],
                text=True,
                encoding="utf-8",
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "published")
            remote_head = subprocess.run(
                ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"],
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=True,
            ).stdout.strip()
            local_head = run_git(project, "rev-parse", "HEAD").stdout.strip()
            self.assertEqual(local_head, remote_head)


if __name__ == "__main__":
    unittest.main()
