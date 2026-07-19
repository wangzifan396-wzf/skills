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


export async function buildReviewSheets(configValue) {
  const resolved = await loadProjectConfig(configValue);
  let renderManifest;
  try {
    renderManifest = JSON.parse(await readFile(path.join(resolved.outputDir, "render-manifest.json"), "utf8"));
  } catch (error) {
    throw new PromoError(`Unable to read render manifest: ${error.message}`);
  }
  const ffmpeg = locateFfmpeg();
  const reviewDir = path.join(resolved.outputDir, "review");
  await mkdir(reviewDir, { recursive: true });
  const sheets = [];
  for (const output of renderManifest.outputs) {
    const input = path.resolve(resolved.outputDir, output.file);
    const target = path.join(reviewDir, `${output.profile}-${output.variant}-contact-sheet.jpg`);
    const tileWidth = output.height > output.width ? 220 : 400;
    const interval = Math.max(0.2, output.duration / 6);
    const filter = `fps=1/${interval.toFixed(4)},scale=${tileWidth}:-2,tile=3x2:padding=8:margin=8:color=0x06101c`;
    await runProcess(ffmpeg, [
      "-hide_banner", "-loglevel", "error", "-y",
      "-i", input,
      "-vf", filter,
      "-frames:v", "1",
      "-q:v", "2",
      target,
    ], { cwd: resolved.outputDir });
    sheets.push({
      profile: output.profile,
      variant: output.variant,
      source: output.file,
      file: path.relative(resolved.outputDir, target).replace(/\\/g, "/"),
      bytes: (await stat(target)).size,
    });
  }
  const manifest = { schemaVersion: 1, generatedAt: nowIso(), sheets };
  await writeJson(path.join(reviewDir, "manifest.json"), manifest);
  return { resolved, manifest };
}


async function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    const result = await buildReviewSheets(args.config);
    console.log(JSON.stringify({ ok: true, sheets: result.manifest.sheets }, null, 2));
  } catch (error) {
    console.error(JSON.stringify({ ok: false, error: error instanceof PromoError ? error.message : error.stack || String(error) }, null, 2));
    process.exitCode = 2;
  }
}


if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
