import { access, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  PromoError,
  loadProjectConfig,
  locateFfprobe,
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


function fpsValue(rate) {
  if (!rate || !rate.includes("/")) return Number(rate);
  const [numerator, denominator] = rate.split("/").map(Number);
  return denominator ? numerator / denominator : 0;
}


function addIssue(issues, severity, code, message, file = null) {
  issues.push({ severity, code, file, message });
}


async function probeFile(ffprobe, file) {
  const result = await runProcess(ffprobe, [
    "-v", "error",
    "-show_entries", "format=duration,size:stream=codec_name,codec_type,width,height,avg_frame_rate,r_frame_rate,sample_rate,channels,pix_fmt",
    "-of", "json",
    file,
  ], { capture: true });
  return JSON.parse(result.stdout);
}


function reportMarkdown(report) {
  const lines = [
    "# Promo video validation",
    "",
    `Validated: \`${report.validatedAt}\``,
    "",
    "| Check | Result |",
    "| --- | ---: |",
    `| Valid | ${report.valid ? "yes" : "no"} |`,
    `| Blockers | ${report.summary.blockers} |`,
    `| Warnings | ${report.summary.warnings} |`,
    `| Videos | ${report.summary.videos} |`,
    `| Review sheets | ${report.summary.reviewSheets} |`,
    "",
    "## Video outputs",
    "",
    "| File | Dimensions | FPS | Duration | Video / audio | Size |",
    "| --- | ---: | ---: | ---: | --- | ---: |",
    ...report.videos.map((video) =>
      `| \`${video.file}\` | ${video.width}×${video.height} | ${video.fps.toFixed(2)} | ${video.duration.toFixed(2)}s | ${video.videoCodec} / ${video.audioCodec} | ${(video.bytes / 1_000_000).toFixed(2)} MB |`
    ),
    "",
    "## Findings",
    "",
    ...(report.issues.length
      ? report.issues.map((item) => `- **${item.severity.toUpperCase()} / ${item.code}**${item.file ? ` \`${item.file}\`` : ""} — ${item.message}`)
      : ["- No findings."]),
    "",
    "## Human visual review",
    "",
    "- [ ] Open every contact sheet and check for blank/black frames.",
    "- [ ] Confirm each interaction reached the intended project state.",
    "- [ ] Confirm subtitles are readable and match the visible scene.",
    "- [ ] Watch at least one complete clean and captioned output with audio.",
    "- [ ] Confirm landscape and vertical compositions are acceptable.",
    "",
  ];
  return lines.join("\n");
}


export async function validateVideo(configValue) {
  const resolved = await loadProjectConfig(configValue);
  const ffprobe = locateFfprobe();
  const renderManifest = await readJson(path.join(resolved.outputDir, "render-manifest.json"), "render manifest");
  const reviewManifest = await readJson(path.join(resolved.outputDir, "review", "manifest.json"), "review manifest");
  const captureReport = await readJson(path.join(resolved.outputDir, "capture-report.json"), "capture report");
  const issues = [];
  if (captureReport.blockers?.length) {
    captureReport.blockers.forEach((item) => addIssue(issues, "blocker", "capture-error", item.message, item.scene));
  }
  if (captureReport.warnings?.length) {
    captureReport.warnings.forEach((item) => addIssue(issues, "warning", "capture-warning", item.message, item.scene));
  }

  const variants = [
    ...(resolved.config.render.clean ? ["clean"] : []),
    ...(resolved.config.render.captioned ? ["captioned"] : []),
  ];
  const expected = new Set(
    resolved.config.render.profiles.flatMap((profile) =>
      variants.map((variant) => `${profile.id}/${variant}`)
    ),
  );
  const videos = [];
  for (const output of renderManifest.outputs || []) {
    const key = `${output.profile}/${output.variant}`;
    expected.delete(key);
    const file = path.resolve(resolved.outputDir, output.file);
    try {
      await access(file);
      const data = await probeFile(ffprobe, file);
      const video = data.streams?.find((stream) => stream.codec_type === "video") || {};
      const audio = data.streams?.find((stream) => stream.codec_type === "audio") || {};
      const duration = Number(data.format?.duration || 0);
      const bytes = Number(data.format?.size || (await stat(file)).size);
      const fps = fpsValue(video.avg_frame_rate || video.r_frame_rate);
      const record = {
        profile: output.profile,
        variant: output.variant,
        file: output.file,
        width: Number(video.width || 0),
        height: Number(video.height || 0),
        fps,
        duration,
        bytes,
        videoCodec: video.codec_name || "unknown",
        pixelFormat: video.pix_fmt || "unknown",
        audioCodec: audio.codec_name || "unknown",
        sampleRate: Number(audio.sample_rate || 0),
        channels: Number(audio.channels || 0),
      };
      videos.push(record);
      if (record.videoCodec !== "h264") addIssue(issues, "blocker", "video-codec", `Expected H.264, found ${record.videoCodec}`, output.file);
      if (record.width !== output.width || record.height !== output.height) {
        addIssue(issues, "blocker", "dimensions", `Expected ${output.width}×${output.height}, found ${record.width}×${record.height}`, output.file);
      }
      if (Math.abs(record.fps - output.fps) > 0.05) addIssue(issues, "blocker", "frame-rate", `Expected ${output.fps} FPS, found ${record.fps}`, output.file);
      if (Math.abs(record.duration - resolved.totalDuration) > 0.4) {
        addIssue(issues, "blocker", "duration", `Expected ${resolved.totalDuration.toFixed(2)}s, found ${record.duration.toFixed(2)}s`, output.file);
      }
      if (record.audioCodec !== "aac" || record.sampleRate !== 48000 || record.channels !== 2) {
        addIssue(issues, "blocker", "audio-stream", `Expected AAC 48kHz stereo, found ${record.audioCodec} ${record.sampleRate}Hz ${record.channels}ch`, output.file);
      }
      if (bytes < 10000) addIssue(issues, "blocker", "small-output", `Output is unexpectedly small (${bytes} bytes)`, output.file);
    } catch (error) {
      addIssue(issues, "blocker", "probe-failed", error.message, output.file);
    }
  }
  for (const key of expected) addIssue(issues, "blocker", "missing-output", `Missing configured output ${key}`);

  for (const sheet of reviewManifest.sheets || []) {
    const file = path.resolve(resolved.outputDir, sheet.file);
    try {
      const info = await stat(file);
      if (!info.isFile() || info.size < 1000) addIssue(issues, "blocker", "review-sheet", "Review sheet is empty or too small", sheet.file);
    } catch (error) {
      addIssue(issues, "blocker", "review-sheet", error.message, sheet.file);
    }
  }
  if ((reviewManifest.sheets || []).length !== (renderManifest.outputs || []).length) {
    addIssue(issues, "blocker", "review-count", "Every rendered video must have a contact sheet");
  }

  const blockerCount = issues.filter((item) => item.severity === "blocker").length;
  const warningCount = issues.filter((item) => item.severity === "warning").length;
  const report = {
    schemaVersion: 1,
    validatedAt: nowIso(),
    valid: blockerCount === 0,
    visualReviewRequired: true,
    ffprobe,
    summary: {
      blockers: blockerCount,
      warnings: warningCount,
      videos: videos.length,
      reviewSheets: (reviewManifest.sheets || []).length,
    },
    videos,
    issues,
  };
  await writeJson(path.join(resolved.outputDir, "validation-report.json"), report);
  await writeFile(path.join(resolved.outputDir, "validation-report.md"), reportMarkdown(report), "utf8");
  return { resolved, report };
}


async function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    const result = await validateVideo(args.config);
    console.log(JSON.stringify({ valid: result.report.valid, ...result.report.summary }, null, 2));
    if (!result.report.valid) process.exitCode = 2;
  } catch (error) {
    console.error(JSON.stringify({ valid: false, error: error instanceof PromoError ? error.message : error.stack || String(error) }, null, 2));
    process.exitCode = 2;
  }
}


if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
