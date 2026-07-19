import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  PromoError,
  assTime,
  escapeAssText,
  loadProjectConfig,
  nowIso,
  parseArgs,
  srtTime,
  writeJson,
} from "./promo_lib.mjs";


function buildSrt(segments) {
  const lines = [];
  segments.forEach((segment, index) => {
    lines.push(
      String(index + 1),
      `${srtTime(segment.start)} --> ${srtTime(segment.end)}`,
      segment.text,
      "",
    );
  });
  return `${lines.join("\n")}\n`;
}


function buildAss(profile, subtitles, segments) {
  const scale = profile.height / 1080;
  const fontSize = Math.max(18, Math.round(subtitles.fontSize * scale));
  const marginV = Math.max(20, Math.round(subtitles.marginV * scale));
  const fontName = subtitles.fontName.replace(/,/g, " ");
  const primary = subtitles.primaryColor || "&H00FFFFFF";
  const outline = subtitles.outlineColor || "&H00101018";
  const lines = [
    "[Script Info]",
    "ScriptType: v4.00+",
    `PlayResX: ${profile.width}`,
    `PlayResY: ${profile.height}`,
    "ScaledBorderAndShadow: yes",
    "WrapStyle: 0",
    "",
    "[V4+ Styles]",
    "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
    `Style: Default,${fontName},${fontSize},${primary},${primary},${outline},&H90060B14,-1,0,0,0,100,100,0,0,3,1,0,2,40,40,${marginV},1`,
    "",
    "[Events]",
    "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ...segments.map((segment) =>
      `Dialogue: 0,${assTime(segment.start)},${assTime(segment.end)},Default,,0,0,0,,${escapeAssText(segment.text)}`
    ),
    "",
  ];
  return lines.join("\n");
}


export async function buildSubtitles(configValue) {
  const resolved = await loadProjectConfig(configValue);
  const segments = resolved.config.narration.segments;
  const targetDir = path.join(resolved.outputDir, "subtitles");
  await mkdir(targetDir, { recursive: true });
  const srt = path.join(targetDir, "promo.srt");
  await writeFile(srt, buildSrt(segments), "utf8");
  const profiles = [];
  for (const profile of resolved.config.render.profiles) {
    const ass = path.join(targetDir, `promo-${profile.id}.ass`);
    await writeFile(ass, buildAss(profile, resolved.config.subtitles, segments), "utf8");
    profiles.push({
      id: profile.id,
      file: path.relative(resolved.outputDir, ass).replace(/\\/g, "/"),
      width: profile.width,
      height: profile.height,
    });
  }
  const manifest = {
    schemaVersion: 1,
    generatedAt: nowIso(),
    segments: segments.length,
    srt: path.relative(resolved.outputDir, srt).replace(/\\/g, "/"),
    profiles,
  };
  await writeJson(path.join(targetDir, "manifest.json"), manifest);
  return { resolved, manifest };
}


async function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    const result = await buildSubtitles(args.config);
    console.log(JSON.stringify({ ok: true, ...result.manifest }, null, 2));
  } catch (error) {
    console.error(JSON.stringify({ ok: false, error: error instanceof PromoError ? error.message : error.stack || String(error) }, null, 2));
    process.exitCode = 2;
  }
}


if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
