import { mkdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  PromoError,
  loadProjectConfig,
  locateFfmpeg,
  nowIso,
  parseArgs,
  runProcess,
  writeJson,
} from "./promo_lib.mjs";


async function readJson(target, label) {
  try {
    return JSON.parse(await readFile(target, "utf8"));
  } catch (error) {
    throw new PromoError(`Unable to read ${label}: ${target}\n${error.message}`);
  }
}


function videoFilter(scene, index, profile, fps) {
  const sizing = profile.fit === "cover"
    ? `scale=${profile.width}:${profile.height}:force_original_aspect_ratio=increase,crop=${profile.width}:${profile.height}`
    : `scale=${profile.width}:${profile.height}:force_original_aspect_ratio=decrease,pad=${profile.width}:${profile.height}:(ow-iw)/2:(oh-ih)/2:color=0x06101c`;
  return `[${index}:v]trim=start=${Number(scene.trimStart || 0).toFixed(3)}:duration=${scene.duration.toFixed(3)},setpts=PTS-STARTPTS,fps=${fps},${sizing},setsar=1,format=yuv420p[v${index}]`;
}


function audioFilters(musicInput, voiceInputs, totalDuration, musicVolume, narrationVolume, voiceDuck) {
  const filters = [
    `[${musicInput}:a]atrim=duration=${totalDuration.toFixed(3)},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=${musicVolume},apad=whole_len=${Math.ceil(totalDuration * 48000)},atrim=duration=${totalDuration.toFixed(3)}[bg]`,
  ];
  if (!voiceInputs.length) {
    filters.push("[bg]anull[aout]");
    return filters;
  }
  const voiceLabels = [];
  voiceInputs.forEach((voice, index) => {
    const duration = voice.end - voice.start;
    const delay = Math.round(voice.start * 1000);
    const label = `voice${index}`;
    filters.push(
      `[${voice.input}:a]atrim=duration=${duration.toFixed(3)},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,adelay=${delay}:all=1,volume=${narrationVolume}[${label}]`,
    );
    voiceLabels.push(`[${label}]`);
  });
  filters.push(`${voiceLabels.join("")}amix=inputs=${voiceLabels.length}:duration=longest:normalize=0[voices]`);
  if (voiceDuck) {
    filters.push(
      "[voices]asplit=2[side][voiceout]",
      "[bg][side]sidechaincompress=threshold=0.035:ratio=8:attack=20:release=350[ducked]",
      "[ducked][voiceout]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[aout]",
    );
  } else {
    filters.push("[bg][voices]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[aout]");
  }
  return filters;
}


function subtitleFilter(profile) {
  return `ass='subtitles/promo-${profile.id}.ass'`;
}


function recordingForProfile(scene, profile) {
  const recording = scene.recordings?.[profile.id] || scene.recordings?.default;
  if (recording?.file) return recording;
  if (scene.file) return { file: scene.file, trimStart: scene.trimStart || 0 };
  throw new PromoError(`Scene ${scene.id} has no recording for profile ${profile.id} and no default recording`);
}


async function renderVariant({ resolved, recordings, audio, narration, profile, variant, ffmpeg, output }) {
  const scenes = recordings.scenes.map((scene) => ({
    ...scene,
    ...recordingForProfile(scene, profile),
  }));
  const sceneInputs = scenes.map((scene) => path.resolve(resolved.outputDir, scene.file));
  const musicPath = path.resolve(resolved.outputDir, audio.file);
  const narrationFiles = narration.segments.filter((segment) => segment.file);
  const args = ["-hide_banner", "-loglevel", "error", "-y"];
  sceneInputs.forEach((file) => args.push("-i", file));
  const musicInput = sceneInputs.length;
  args.push("-stream_loop", "-1", "-i", musicPath);
  const voiceInputs = [];
  narrationFiles.forEach((segment, index) => {
    const input = musicInput + 1 + index;
    args.push("-i", path.resolve(resolved.outputDir, segment.file));
    voiceInputs.push({ ...segment, input });
  });

  const filters = scenes.map((scene, index) =>
    videoFilter(scene, index, profile, resolved.config.render.fps)
  );
  const labels = scenes.map((_, index) => `[v${index}]`).join("");
  filters.push(`${labels}concat=n=${scenes.length}:v=1:a=0[vbase]`);
  if (variant === "captioned" && resolved.config.narration.segments.length) {
    filters.push(`[vbase]${subtitleFilter(profile)}[vout]`);
  } else {
    filters.push("[vbase]null[vout]");
  }
  filters.push(...audioFilters(
    musicInput,
    voiceInputs,
    resolved.totalDuration,
    resolved.config.audio.musicVolume,
    resolved.config.narration.volume,
    resolved.config.audio.voiceDuck,
  ));

  args.push(
    "-filter_complex", filters.join(";"),
    "-map", "[vout]",
    "-map", "[aout]",
    "-t", resolved.totalDuration.toFixed(3),
    "-r", String(resolved.config.render.fps),
    "-c:v", "libx264",
    "-preset", resolved.config.render.preset,
    "-crf", String(resolved.config.render.crf),
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-b:a", "192k",
    "-ar", "48000",
    "-ac", "2",
    "-movflags", "+faststart",
    output,
  );
  await runProcess(ffmpeg, args, { cwd: resolved.outputDir });
}


export async function renderVideo(configValue) {
  const resolved = await loadProjectConfig(configValue);
  const recordings = await readJson(path.join(resolved.outputDir, "recordings", "manifest.json"), "recordings manifest");
  const audio = await readJson(path.join(resolved.outputDir, "audio", "manifest.json"), "audio manifest");
  const narration = await readJson(path.join(resolved.outputDir, "narration", "manifest.json"), "narration manifest");
  if (recordings.scenes.length !== resolved.scenes.length) {
    throw new PromoError("Recordings manifest does not match configured scene count");
  }
  const videosDir = path.join(resolved.outputDir, "videos");
  await mkdir(videosDir, { recursive: true });
  const ffmpeg = locateFfmpeg();
  const outputs = [];
  const variants = [];
  if (resolved.config.render.clean) variants.push("clean");
  if (resolved.config.render.captioned) variants.push("captioned");
  for (const profile of resolved.config.render.profiles) {
    for (const variant of variants) {
      const output = path.join(videosDir, `promo-${profile.id}-${variant}.mp4`);
      await renderVariant({ resolved, recordings, audio, narration, profile, variant, ffmpeg, output });
      outputs.push({
        profile: profile.id,
        variant,
        width: profile.width,
        height: profile.height,
        fps: resolved.config.render.fps,
        duration: resolved.totalDuration,
        file: path.relative(resolved.outputDir, output).replace(/\\/g, "/"),
        bytes: (await stat(output)).size,
      });
    }
  }
  const manifest = {
    schemaVersion: 1,
    generatedAt: nowIso(),
    ffmpeg,
    outputs,
  };
  await writeJson(path.join(resolved.outputDir, "render-manifest.json"), manifest);
  const recordingFiles = [...new Set(recordings.scenes.flatMap((scene) => {
    if (scene.recordings) return Object.values(scene.recordings).map((recording) => recording.file);
    return scene.file ? [scene.file] : [];
  }))];
  await writeJson(path.join(resolved.outputDir, "editable-manifest.json"), {
    schemaVersion: 1,
    generatedAt: nowIso(),
    recordings: recordingFiles,
    narration: narration.segments.filter((segment) => segment.file).map((segment) => segment.file),
    audio: [audio.file],
    subtitles: ["subtitles/promo.srt", ...resolved.config.render.profiles.map((profile) => `subtitles/promo-${profile.id}.ass`)],
    videos: outputs.map((item) => item.file),
  });
  return { resolved, manifest };
}


async function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    const result = await renderVideo(args.config);
    console.log(JSON.stringify({ ok: true, outputs: result.manifest.outputs }, null, 2));
  } catch (error) {
    console.error(JSON.stringify({ ok: false, error: error instanceof PromoError ? error.message : error.stack || String(error) }, null, 2));
    process.exitCode = 2;
  }
}


if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
