import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  PromoError,
  SCRIPT_DIR,
  loadProjectConfig,
  parseArgs,
  prepareOutput,
  pythonCommand,
  runProcess,
} from "./promo_lib.mjs";


async function requireFile(target, label) {
  try {
    await access(target);
  } catch {
    throw new PromoError(`${label} does not exist: ${target}`);
  }
}


async function runNode(script, config) {
  await runProcess(process.execPath, [path.join(SCRIPT_DIR, script), "--config", config]);
}


export async function buildPromoVideo(args) {
  const resolved = await loadProjectConfig(args.config);
  const preserve = args.skipCapture ? ["recordings", "capture-report.json"] : [];
  await prepareOutput(resolved, args.force, preserve);
  const config = resolved.configPath;

  await runNode("inspect_project.mjs", config);
  if (args.skipCapture) {
    await requireFile(path.join(resolved.outputDir, "recordings", "manifest.json"), "Recordings manifest for --skip-capture");
    await requireFile(path.join(resolved.outputDir, "capture-report.json"), "Capture report for --skip-capture");
  } else {
    await runNode("capture_scenes.mjs", config);
  }
  await runProcess(pythonCommand(), [path.join(SCRIPT_DIR, "generate_narration.py"), "--config", config]);
  await runNode("generate_audio.mjs", config);
  await runNode("build_subtitles.mjs", config);
  await runNode("render_video.mjs", config);
  await runNode("build_review_sheets.mjs", config);
  await runNode("validate_video.mjs", config);

  const validation = JSON.parse(await readFile(path.join(resolved.outputDir, "validation-report.json"), "utf8"));
  return { resolved, validation };
}


async function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    const result = await buildPromoVideo(args);
    console.log(JSON.stringify({
      ok: result.validation.valid,
      output: result.resolved.outputDir,
      ...result.validation.summary,
      visualReviewRequired: result.validation.visualReviewRequired,
    }, null, 2));
    if (!result.validation.valid) process.exitCode = 2;
  } catch (error) {
    console.error(JSON.stringify({ ok: false, error: error instanceof PromoError ? error.message : error.stack || String(error) }, null, 2));
    process.exitCode = 2;
  }
}


if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
