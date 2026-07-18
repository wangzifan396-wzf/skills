from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "github-safe-publish" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import inspect_project  # noqa: E402
import prepare_gitignore  # noqa: E402
import publish_project  # noqa: E402
from publish_lib import PublishError, parse_github_remote  # noqa: E402


class RemoteParsingTests(unittest.TestCase):
    def test_https_and_ssh_urls_normalize_to_same_slug(self) -> None:
        values = [
            "https://github.com/example/demo",
            "https://github.com/example/demo.git",
            "git@github.com:example/demo.git",
            "ssh://git@github.com/example/demo.git",
        ]
        self.assertEqual({parse_github_remote(value).slug for value in values}, {"example/demo"})

    def test_embedded_https_credentials_are_rejected(self) -> None:
        with self.assertRaises(PublishError):
            parse_github_remote("https://token-value@github.com/example/demo.git")

    def test_non_repository_github_paths_are_rejected(self) -> None:
        with self.assertRaises(PublishError):
            parse_github_remote("https://github.com/example/demo/tree/main")

    def test_confirmation_must_match_url(self) -> None:
        with self.assertRaises(PublishError):
            publish_project.validate_confirmation("example/wrong", "example/demo")


class ProjectInspectionTests(unittest.TestCase):
    def test_clean_static_project_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text("# Demo\n\nOpen index.html.\n", encoding="utf-8")
            (root / "LICENSE").write_text("MIT test fixture\n", encoding="utf-8")
            (root / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
            (root / "index.html").write_text("<!doctype html><title>Demo</title>\n", encoding="utf-8")
            dependencies = root / "node_modules"
            dependencies.mkdir()
            (dependencies / "package.js").write_text("ignored\n", encoding="utf-8")

            manifest = inspect_project.build_manifest(root)
            self.assertEqual(manifest["summary"]["blockers"], 0)
            self.assertEqual(manifest["project"]["types"], ["static web"])
            self.assertIn("index.html", [item["path"] for item in manifest["candidateFiles"]])
            self.assertNotIn("node_modules/package.js", [item["path"] for item in manifest["candidateFiles"]])
            self.assertTrue(any(item["path"] == "node_modules/" for item in manifest["excludedPaths"]))

    def test_secret_is_blocked_but_never_copied_to_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            secret_value = "super-private-value-12345"
            (root / "config.txt").write_text(f"api_key={secret_value}\n", encoding="utf-8")

            manifest = inspect_project.build_manifest(root)
            serialized = json.dumps(manifest)
            self.assertGreaterEqual(manifest["summary"]["blockers"], 1)
            self.assertNotIn(secret_value, serialized)
            self.assertTrue(any(item["code"] == "credential-assignment" for item in manifest["findings"]))

    def test_env_template_is_allowed_but_real_env_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env.example").write_text("API_KEY=your_key_here\n", encoding="utf-8")
            template_manifest = inspect_project.build_manifest(root)
            self.assertEqual(template_manifest["summary"]["blockers"], 0)

            (root / ".env").write_text("API_KEY=not-a-real-test-value\n", encoding="utf-8")
            real_manifest = inspect_project.build_manifest(root)
            self.assertTrue(any(item["code"] == "sensitive-filename" for item in real_manifest["findings"]))

    def test_large_file_limit_is_a_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "archive.bin"
            path.write_bytes(b"x" * 65)
            original_limit = inspect_project.GITHUB_MAX_FILE_BYTES
            original_warning = inspect_project.LARGE_FILE_WARNING_BYTES
            try:
                inspect_project.GITHUB_MAX_FILE_BYTES = 64
                inspect_project.LARGE_FILE_WARNING_BYTES = 32
                manifest = inspect_project.build_manifest(root)
            finally:
                inspect_project.GITHUB_MAX_FILE_BYTES = original_limit
                inspect_project.LARGE_FILE_WARNING_BYTES = original_warning
            self.assertTrue(any(item["code"] == "github-file-limit" for item in manifest["findings"]))

    def test_git_scanner_respects_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "--initial-branch=main"], cwd=root, check=True, capture_output=True)
            (root / ".gitignore").write_text("*.log\n", encoding="utf-8")
            (root / "README.md").write_text("# Git fixture\n", encoding="utf-8")
            (root / "debug.log").write_text("local log\n", encoding="utf-8")

            manifest = inspect_project.build_manifest(root)
            candidates = [item["path"] for item in manifest["candidateFiles"]]
            self.assertIn("README.md", candidates)
            self.assertNotIn("debug.log", candidates)
            self.assertTrue(any(item["path"] == "debug.log" for item in manifest["excludedPaths"]))


class GitignorePreparationTests(unittest.TestCase):
    def test_write_is_ordered_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env").write_text("API_KEY=not-a-real-test-value\n", encoding="utf-8")
            (root / ".env.example").write_text("API_KEY=your_key_here\n", encoding="utf-8")
            first = prepare_gitignore.plan(root)
            prepare_gitignore.apply_plan(first)
            content = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertLess(content.index(".env.*"), content.index("!.env.example"))

            second = prepare_gitignore.plan(root)
            self.assertFalse(second["changed"])


if __name__ == "__main__":
    unittest.main()
