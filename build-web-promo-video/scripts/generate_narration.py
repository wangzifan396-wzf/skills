from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_config(path: Path) -> tuple[dict[str, Any], Path, Path]:
    config_path = path.expanduser().resolve()
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read configuration: {exc}") from exc
    output_dir = (config_path.parent / config["output"]["directory"]).resolve()
    return config, config_path.parent, output_dir


async def synthesize_edge_tts(text: str, target: Path, narration: dict[str, Any]) -> None:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError(
            "edge-tts is not installed. Install scripts/requirements.txt or choose provider none/files."
        ) from exc
    communicate = edge_tts.Communicate(
        text,
        narration.get("voice", "zh-CN-YunyangNeural"),
        rate=narration.get("rate", "+0%"),
        pitch=narration.get("pitch", "+0Hz"),
        volume="+0%",
    )
    await communicate.save(str(target))


async def generate(config_path: Path) -> dict[str, Any]:
    config, config_dir, output_dir = load_config(config_path)
    narration = config["narration"]
    provider = narration["provider"]
    target_dir = output_dir / "narration"
    target_dir.mkdir(parents=True, exist_ok=True)
    output_segments: list[dict[str, Any]] = []

    for index, segment in enumerate(narration.get("segments", []), start=1):
        item = {
            "number": index,
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"],
            "file": None,
        }
        if provider == "files":
            source = (config_dir / segment["file"]).resolve()
            if not source.is_file():
                raise RuntimeError(f"Narration source does not exist: {source}")
            target = target_dir / f"{index:02d}{source.suffix.lower()}"
            shutil.copy2(source, target)
            item["file"] = target.relative_to(output_dir).as_posix()
        elif provider == "edge-tts":
            target = target_dir / f"{index:02d}.mp3"
            await synthesize_edge_tts(segment["text"], target, narration)
            item["file"] = target.relative_to(output_dir).as_posix()
        output_segments.append(item)

    manifest = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "provider": provider,
        "voice": narration.get("voice") if provider == "edge-tts" else None,
        "volume": narration.get("volume", 1),
        "segments": output_segments,
    }
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or copy optional narration segments")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = asyncio.run(generate(args.config))
        print(
            json.dumps(
                {
                    "ok": True,
                    "provider": manifest["provider"],
                    "segments": len(manifest["segments"]),
                    "audioFiles": sum(1 for item in manifest["segments"] if item["file"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:  # user-facing CLI boundary
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
