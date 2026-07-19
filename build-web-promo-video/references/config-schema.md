# Video project configuration

Use `assets/config-template/video-project.json` as the starting point.

## Paths

- Resolve `project.root`, `output.directory`, supplied clips, supplied music, and narration files
  relative to the configuration file.
- Resolve page `path` and adapter paths below `project.root`.
- Keep output outside the source tree when possible.

## Project and capture

- `schemaVersion`: must be `1`.
- `project.name`: non-empty display name.
- `project.root`: local web root.
- `capture.baseUrl`: optional existing HTTP(S) origin. Leave empty to start the built-in static
  server for page scenes.
- `capture.browserChannel`: optional Playwright channel.
- `capture.headless`: boolean.
- `capture.perProfile`: when `true`, record browser scenes once per render profile using that
  profile's viewport. Prefer this for responsive pages and mixed landscape/vertical output. When
  `false`, record once with `capture.viewport` and scale/crop that recording for every profile.
- `capture.viewport`: positive width and height.
- `capture.postLoadWaitMs`: settling delay after navigation.

## Scenes

Provide 1-24 scenes. Each scene requires a unique lowercase `id`, `title`, and `duration` in seconds.
Use exactly one source:

- `path`: page below the project root; query strings are allowed.
- `url`: HTTP(S) page.
- `clip`: existing local video.

Optional `adapter` points to a reviewed module below the project root. Optional `actions` follow
`references/capture-adapters.md`.

## Narration and subtitles

- `narration.provider`: `none`, `files`, or `edge-tts`.
- `narration.voice`, `rate`, `pitch`: Edge TTS options.
- `narration.volume`: render volume.
- `narration.segments`: ordered `start`, `end`, `text`, and optional `file` entries.
- `subtitles.fontName`, `fontSize`, `marginV`, and color fields control generated ASS files.

Subtitle segments may exist with provider `none`.

## Audio

- `audio.mode`: `procedural`, `file`, or `none`.
- `audio.file`: required for file mode.
- `audio.bpm`, `seed`: procedural controls.
- `audio.musicVolume`: background volume in the final mix.
- `audio.voiceDuck`: enable narration sidechain ducking.

## Render

- `render.fps`: 24, 25, 30, or 60.
- `render.crf`: H.264 quality value, normally 16-28.
- `render.preset`: FFmpeg x264 preset.
- `render.clean` / `captioned`: requested variants.
- `render.profiles`: unique profiles with even `width`/`height` and `fit` set to `contain` or
  `cover`.

The total video duration is the sum of scene durations. Narration segments must fit within it.

## Output safety

The orchestrator writes a marker file into the output directory. `--force` may clean only known
generated paths in an already marked directory. It refuses a non-empty unmarked directory.
