import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  PromoError,
  formatClock,
  loadProjectConfig,
  nowIso,
  parseArgs,
  platformSummary,
  verifySourceFiles,
  writeJson,
} from "./promo_lib.mjs";


export async function inspectProject(configValue) {
  const resolved = await loadProjectConfig(configValue);
  await verifySourceFiles(resolved);

  let cursor = 0;
  const timeline = resolved.scenes.map((scene, index) => {
    const start = cursor;
    const end = start + scene.duration;
    cursor = end;
    return {
      index: index + 1,
      id: scene.id,
      title: scene.title,
      sourceType: scene.sourceType,
      source: scene.source,
      start,
      end,
      duration: scene.duration,
      actions: scene.actions.length,
      adapter: scene.adapter ? scene.adapter : null,
    };
  });

  const facts = {
    schemaVersion: 1,
    generatedAt: nowIso(),
    project: {
      name: resolved.projectName,
      root: resolved.projectRoot,
      configuration: resolved.configPath,
    },
    duration: resolved.totalDuration,
    sceneCount: resolved.scenes.length,
    actionCount: resolved.scenes.reduce((sum, scene) => sum + scene.actions.length, 0),
    sources: Object.fromEntries(
      ["path", "url", "clip"].map((sourceType) => [
        sourceType,
        resolved.scenes.filter((scene) => scene.sourceType === sourceType).length,
      ]),
    ),
    narration: {
      provider: resolved.config.narration.provider,
      segments: resolved.config.narration.segments.length,
    },
    capture: {
      perProfile: resolved.config.capture.perProfile ?? false,
      viewport: resolved.config.capture.viewport,
      targets: (resolved.config.capture.perProfile
        ? resolved.config.render.profiles.map((profile) => ({
            id: profile.id,
            width: profile.width,
            height: profile.height,
          }))
        : [{ id: "default", ...resolved.config.capture.viewport }]),
    },
    audio: { mode: resolved.config.audio.mode },
    render: {
      fps: resolved.config.render.fps,
      clean: resolved.config.render.clean,
      captioned: resolved.config.render.captioned,
      profiles: resolved.config.render.profiles,
    },
    output: resolved.outputDir,
    environment: platformSummary(),
  };

  const storyboard = [
    `# ${resolved.projectName} promo storyboard`,
    "",
    `Total duration: **${resolved.totalDuration.toFixed(2)} seconds**`,
    "",
    "| # | Time | Scene | Source | Actions | Adapter |",
    "| ---: | --- | --- | --- | ---: | --- |",
    ...timeline.map((scene) =>
      `| ${scene.index} | ${formatClock(scene.start)}–${formatClock(scene.end)} | ${scene.title} | ${scene.sourceType}: \`${scene.source}\` | ${scene.actions} | ${scene.adapter ? `\`${scene.adapter}\`` : "—"} |`
    ),
    "",
    "## Narration",
    "",
    ...(resolved.config.narration.segments.length
      ? resolved.config.narration.segments.map((segment, index) =>
        `${index + 1}. **${formatClock(segment.start)}–${formatClock(segment.end)}** — ${segment.text}`
      )
      : ["No narration/subtitle segments configured."]),
    "",
    "## Capture",
    "",
    resolved.config.capture.perProfile
      ? "Browser scenes are recorded separately for every output profile."
      : `Browser scenes are recorded once at ${resolved.config.capture.viewport.width}x${resolved.config.capture.viewport.height}.`,
    "",
    "## Output profiles",
    "",
    ...resolved.config.render.profiles.map((profile) =>
      `- **${profile.id}**: ${profile.width}×${profile.height}, ${profile.fit}, ${resolved.config.render.fps} FPS`
    ),
    "",
  ].join("\n");

  await writeJson(path.join(resolved.outputDir, "project-facts.json"), facts);
  await writeJson(path.join(resolved.outputDir, "timeline.json"), {
    schemaVersion: 1,
    generatedAt: nowIso(),
    duration: resolved.totalDuration,
    scenes: timeline,
  });
  await import("node:fs/promises").then(({ mkdir, writeFile }) =>
    mkdir(resolved.outputDir, { recursive: true }).then(() =>
      writeFile(path.join(resolved.outputDir, "storyboard.md"), storyboard, "utf8")
    )
  );
  return { resolved, facts, timeline };
}


async function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    const result = await inspectProject(args.config);
    console.log(JSON.stringify({
      ok: true,
      project: result.facts.project.name,
      scenes: result.facts.sceneCount,
      duration: result.facts.duration,
      profiles: result.facts.render.profiles.map((profile) => profile.id),
      output: result.facts.output,
    }, null, 2));
  } catch (error) {
    const message = error instanceof PromoError ? error.message : error.stack || String(error);
    console.error(JSON.stringify({ ok: false, error: message }, null, 2));
    process.exitCode = 2;
  }
}


if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
