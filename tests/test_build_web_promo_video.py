from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "build-web-promo-video"
SCRIPTS = SKILL / "scripts"
FIXTURE = SKILL / "assets" / "demo-project"


def run_node(script: str, config: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(SCRIPTS / script), "--config", str(config), *extra],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WebPromoVideoTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> Path:
        project = root / "demo-project"
        shutil.copytree(FIXTURE, project)
        return project / "video-project.json"

    def test_inspection_generates_storyboard_timeline_and_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_fixture(Path(temporary))
            result = run_node("inspect_project.mjs", config)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = config.parent / "promo-output"
            facts = json.loads((output / "project-facts.json").read_text(encoding="utf-8"))
            timeline = json.loads((output / "timeline.json").read_text(encoding="utf-8"))
            self.assertEqual(facts["sceneCount"], 2)
            self.assertEqual(facts["duration"], 5)
            self.assertTrue(facts["capture"]["perProfile"])
            self.assertEqual([item["id"] for item in facts["capture"]["targets"]], ["landscape", "vertical"])
            self.assertEqual(timeline["scenes"][1]["start"], 2.5)
            self.assertIn("Launch sequence", (output / "storyboard.md").read_text(encoding="utf-8"))

    def test_procedural_audio_is_deterministic_and_subtitles_match_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_fixture(Path(temporary))
            first = run_node("generate_audio.mjs", config)
            self.assertEqual(first.returncode, 0, first.stderr)
            audio = config.parent / "promo-output" / "audio" / "music.wav"
            first_hash = sha256(audio)
            second = run_node("generate_audio.mjs", config)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(first_hash, sha256(audio))
            self.assertEqual(audio.read_bytes()[:4], b"RIFF")

            subtitles = run_node("build_subtitles.mjs", config)
            self.assertEqual(subtitles.returncode, 0, subtitles.stderr)
            output = config.parent / "promo-output" / "subtitles"
            self.assertTrue((output / "promo-landscape.ass").is_file())
            self.assertTrue((output / "promo-vertical.ass").is_file())
            landscape_ass = (output / "promo-landscape.ass").read_text(encoding="utf-8")
            self.assertIn("WrapStyle: 0", landscape_ass)
            self.assertIn("Dialogue:", landscape_ass)

    def test_clip_capture_uses_default_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_fixture(Path(temporary))
            clip = config.parent / "supplied.webm"
            clip.write_bytes(b"fixture clip")
            payload = json.loads(config.read_text(encoding="utf-8"))
            payload["scenes"] = [
                {
                    "id": "supplied",
                    "title": "Supplied clip",
                    "clip": "supplied.webm",
                    "duration": 2,
                    "clipStart": 0.25,
                    "actions": [],
                }
            ]
            payload["narration"]["segments"] = [
                {"start": 0, "end": 2, "text": "A supplied clip remains reusable across profiles."}
            ]
            config.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = run_node("capture_scenes.mjs", config)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(
                (config.parent / "promo-output" / "recordings" / "manifest.json").read_text(encoding="utf-8")
            )
            recording = manifest["scenes"][0]["recordings"]["default"]
            self.assertEqual(recording["file"], "recordings/supplied.webm")
            self.assertEqual(recording["trimStart"], 0.25)
            self.assertEqual(
                (config.parent / "promo-output" / recording["file"]).read_bytes(),
                clip.read_bytes(),
            )

    def test_none_narration_writes_timed_manifest_without_audio_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_fixture(Path(temporary))
            result = subprocess.run(
                ["python", str(SCRIPTS / "generate_narration.py"), "--config", str(config)],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(
                (config.parent / "promo-output" / "narration" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["provider"], "none")
            self.assertEqual(len(manifest["segments"]), 2)
            self.assertTrue(all(item["file"] is None for item in manifest["segments"]))

    def test_missing_scene_source_and_unmarked_output_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_fixture(Path(temporary))
            payload = json.loads(config.read_text(encoding="utf-8"))
            payload["scenes"][0]["path"] = "missing.html"
            config.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            missing = run_node("inspect_project.mjs", config)
            self.assertEqual(missing.returncode, 2)
            self.assertIn("Missing source files", missing.stderr)

        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_fixture(Path(temporary))
            output = config.parent / "promo-output"
            output.mkdir()
            (output / "user-file.txt").write_text("preserve me\n", encoding="utf-8")
            blocked = run_node("build_promo_video.mjs", config)
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("unmarked output directory", blocked.stderr)
            self.assertEqual((output / "user-file.txt").read_text(encoding="utf-8"), "preserve me\n")

        with tempfile.TemporaryDirectory() as temporary:
            config = self.make_fixture(Path(temporary))
            payload = json.loads(config.read_text(encoding="utf-8"))
            payload["capture"]["perProfile"] = "yes"
            config.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            invalid = run_node("inspect_project.mjs", config)
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("capture.perProfile must be a boolean", invalid.stderr)


if __name__ == "__main__":
    unittest.main()
