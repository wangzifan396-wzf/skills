# Media environment

## Required

- Node.js 20 or newer.
- Dependencies installed from `scripts/package.json`.
- A Playwright-compatible Chromium browser for browser scenes.
- A full FFmpeg and FFprobe installation with H.264/AAC encoders and ASS subtitle support.

Install script dependencies:

```text
cd <skill>/scripts
npm install
npx playwright install chromium
```

Prefer tools already installed by the user. Do not bundle browser or FFmpeg binaries in the Skill.

## Tool discovery

The scripts try:

1. `FFMPEG_PATH` / `FFPROBE_PATH`;
2. `ffmpeg` / `ffprobe` on `PATH`;
3. an `ffprobe-static` development dependency when installed.

Set `PLAYWRIGHT_CHANNEL=msedge` or `chrome` to use an installed browser channel. Otherwise use the
Playwright-managed Chromium executable.

## Optional Edge TTS

Install only when `narration.provider` is `edge-tts`:

```text
python -m pip install -r <skill>/scripts/requirements.txt
```

TTS requires network access and may fail because of service availability or policy. Support
`provider: files` and `provider: none` as offline fallbacks.

## Fonts

ASS subtitles name a system font but do not bundle it. Select a font installed on the render
machine and verify Chinese glyphs in the contact sheet. Do not copy commercial/system font files
into the Skill.
