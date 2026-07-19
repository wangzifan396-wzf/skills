import { createHash } from "node:crypto";
import { access, mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { spawn, spawnSync } from "node:child_process";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";


export const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
export const OUTPUT_MARKER = ".build-web-promo-video.json";
export const GENERATED_PATHS = [
  "project-facts.json",
  "storyboard.md",
  "timeline.json",
  "recordings",
  "narration",
  "audio",
  "subtitles",
  "videos",
  "review",
  "capture-report.json",
  "render-manifest.json",
  "editable-manifest.json",
  "validation-report.json",
  "validation-report.md",
];


export class PromoError extends Error {}


export function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}


export async function exists(target) {
  try {
    await access(target);
    return true;
  } catch {
    return false;
  }
}


export function parseArgs(argv, options = {}) {
  const result = { force: false, skipCapture: false, ...options.defaults };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--config") result.config = argv[++index];
    else if (value === "--force") result.force = true;
    else if (value === "--skip-capture") result.skipCapture = true;
    else if (value === "--json-out") result.jsonOut = argv[++index];
    else if (value === "--report-out") result.reportOut = argv[++index];
    else throw new PromoError(`Unknown argument: ${value}`);
  }
  if (!result.config) throw new PromoError("--config is required");
  return result;
}


function ensureObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new PromoError(`${label} must be an object`);
  }
  return value;
}


function ensureText(value, label) {
  if (typeof value !== "string" || !value.trim()) throw new PromoError(`${label} must be a non-empty string`);
  return value.trim();
}


function ensureNumber(value, label, minimum, maximum) {
  if (!Number.isFinite(value) || value < minimum || value > maximum) {
    throw new PromoError(`${label} must be between ${minimum} and ${maximum}`);
  }
  return value;
}


function ensureBoolean(value, label) {
  if (typeof value !== "boolean") throw new PromoError(`${label} must be a boolean`);
  return value;
}


function isInside(parent, child) {
  const relative = path.relative(parent, child);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}


function resolveBelow(parent, relative, label) {
  const target = path.resolve(parent, relative);
  if (!isInside(parent, target)) throw new PromoError(`${label} must stay below ${parent}`);
  return target;
}


function pageFileFromPath(projectRoot, pagePath, label) {
  const pathname = pagePath.split(/[?#]/, 1)[0] || "index.html";
  return resolveBelow(projectRoot, pathname, label);
}


function validateAction(action, scene, index) {
  ensureObject(action, `scene ${scene.id} action ${index + 1}`);
  ensureNumber(action.at, `scene ${scene.id} action ${index + 1}.at`, 0, scene.duration);
  const type = ensureText(action.type, `scene ${scene.id} action ${index + 1}.type`);
  const allowed = new Set(["click", "press", "type", "mouseMove", "mouseDown", "mouseUp", "scroll", "wait"]);
  if (!allowed.has(type)) throw new PromoError(`Unsupported action type '${type}' in scene ${scene.id}`);
  if (type === "click" && !action.selector) throw new PromoError(`click action in ${scene.id} requires selector`);
  if (type === "press" && !action.key) throw new PromoError(`press action in ${scene.id} requires key`);
  if (type === "type" && (!action.selector || typeof action.text !== "string")) {
    throw new PromoError(`type action in ${scene.id} requires selector and text`);
  }
  if (type === "mouseMove") {
    ensureNumber(action.x, `scene ${scene.id} mouseMove.x`, 0, 10000);
    ensureNumber(action.y, `scene ${scene.id} mouseMove.y`, 0, 10000);
  }
  if (type === "scroll") {
    if (!Number.isFinite(action.deltaX ?? 0) || !Number.isFinite(action.deltaY ?? 0)) {
      throw new PromoError(`scroll action in ${scene.id} requires numeric deltaX/deltaY`);
    }
  }
}


export async function loadProjectConfig(configValue) {
  const configPath = path.resolve(configValue);
  let raw;
  try {
    raw = await readFile(configPath, "utf8");
  } catch (error) {
    throw new PromoError(`Unable to read configuration: ${error.message}`);
  }
  let config;
  try {
    config = JSON.parse(raw);
  } catch (error) {
    throw new PromoError(`Invalid configuration JSON: ${error.message}`);
  }
  ensureObject(config, "configuration");
  if (config.schemaVersion !== 1) throw new PromoError("schemaVersion must be 1");
  const configDir = path.dirname(configPath);

  const project = ensureObject(config.project, "project");
  const projectName = ensureText(project.name, "project.name");
  const projectRoot = path.resolve(configDir, ensureText(project.root, "project.root"));
  if (!(await exists(projectRoot)) || !(await stat(projectRoot)).isDirectory()) {
    throw new PromoError(`project.root does not exist or is not a directory: ${projectRoot}`);
  }

  const output = ensureObject(config.output, "output");
  const outputDir = path.resolve(configDir, ensureText(output.directory, "output.directory"));

  const capture = ensureObject(config.capture, "capture");
  const viewport = ensureObject(capture.viewport, "capture.viewport");
  ensureNumber(viewport.width, "capture.viewport.width", 320, 4096);
  ensureNumber(viewport.height, "capture.viewport.height", 320, 4096);
  ensureBoolean(capture.perProfile ?? false, "capture.perProfile");
  ensureBoolean(capture.headless, "capture.headless");
  ensureNumber(capture.postLoadWaitMs ?? 500, "capture.postLoadWaitMs", 0, 30000);
  if (capture.baseUrl && !/^https?:\/\//i.test(capture.baseUrl)) {
    throw new PromoError("capture.baseUrl must be empty or an HTTP(S) URL");
  }

  if (!Array.isArray(config.scenes) || config.scenes.length < 1 || config.scenes.length > 24) {
    throw new PromoError("scenes must contain 1-24 entries");
  }
  const sceneIds = new Set();
  let totalDuration = 0;
  const scenes = [];
  for (let index = 0; index < config.scenes.length; index += 1) {
    const input = ensureObject(config.scenes[index], `scenes[${index}]`);
    const id = ensureText(input.id, `scenes[${index}].id`);
    if (!/^[a-z0-9][a-z0-9-]{0,47}$/.test(id)) throw new PromoError(`Invalid scene id: ${id}`);
    if (sceneIds.has(id)) throw new PromoError(`Duplicate scene id: ${id}`);
    sceneIds.add(id);
    const title = ensureText(input.title, `scene ${id}.title`);
    const duration = ensureNumber(input.duration, `scene ${id}.duration`, 1, 120);
    const sourceKeys = ["path", "url", "clip"].filter((key) => typeof input[key] === "string" && input[key].trim());
    if (sourceKeys.length !== 1) throw new PromoError(`scene ${id} must define exactly one of path, url, or clip`);
    const sourceType = sourceKeys[0];
    let source;
    let sourceFile = null;
    if (sourceType === "path") {
      source = input.path.trim();
      sourceFile = pageFileFromPath(projectRoot, source, `scene ${id}.path`);
    } else if (sourceType === "url") {
      source = input.url.trim();
      if (!/^https?:\/\//i.test(source)) throw new PromoError(`scene ${id}.url must be HTTP(S)`);
    } else {
      source = input.clip.trim();
      sourceFile = path.resolve(configDir, source);
    }
    let adapterFile = null;
    if (input.adapter) adapterFile = resolveBelow(projectRoot, input.adapter, `scene ${id}.adapter`);
    const actions = input.actions ?? [];
    if (!Array.isArray(actions)) throw new PromoError(`scene ${id}.actions must be an array`);
    actions.forEach((action, actionIndex) => validateAction(action, { id, duration }, actionIndex));
    for (let actionIndex = 1; actionIndex < actions.length; actionIndex += 1) {
      if (actions[actionIndex].at < actions[actionIndex - 1].at) {
        throw new PromoError(`scene ${id} actions must be sorted by at`);
      }
    }
    scenes.push({ ...input, id, title, duration, sourceType, source, sourceFile, adapterFile, actions });
    totalDuration += duration;
  }
  if (totalDuration > 600) throw new PromoError("Total duration must not exceed 600 seconds in V1");

  const narration = ensureObject(config.narration, "narration");
  const providers = new Set(["none", "files", "edge-tts"]);
  if (!providers.has(narration.provider)) throw new PromoError("narration.provider must be none, files, or edge-tts");
  ensureNumber(narration.volume ?? 1, "narration.volume", 0, 4);
  const segments = narration.segments ?? [];
  if (!Array.isArray(segments)) throw new PromoError("narration.segments must be an array");
  let previousStart = -1;
  for (let index = 0; index < segments.length; index += 1) {
    const segment = ensureObject(segments[index], `narration.segments[${index}]`);
    const start = ensureNumber(segment.start, `narration segment ${index + 1}.start`, 0, totalDuration);
    const end = ensureNumber(segment.end, `narration segment ${index + 1}.end`, start + 0.05, totalDuration);
    ensureText(segment.text, `narration segment ${index + 1}.text`);
    if (start < previousStart) throw new PromoError("narration segments must be sorted by start");
    previousStart = start;
    if (narration.provider === "files" && !segment.file) {
      throw new PromoError(`narration segment ${index + 1} requires file for provider files`);
    }
  }

  const subtitles = ensureObject(config.subtitles, "subtitles");
  ensureText(subtitles.fontName, "subtitles.fontName");
  ensureNumber(subtitles.fontSize, "subtitles.fontSize", 12, 120);
  ensureNumber(subtitles.marginV, "subtitles.marginV", 0, 500);

  const audio = ensureObject(config.audio, "audio");
  if (!new Set(["procedural", "file", "none"]).has(audio.mode)) {
    throw new PromoError("audio.mode must be procedural, file, or none");
  }
  if (audio.mode === "file" && !audio.file) throw new PromoError("audio.file is required for file mode");
  ensureNumber(audio.musicVolume ?? 0.42, "audio.musicVolume", 0, 2);
  ensureBoolean(audio.voiceDuck ?? true, "audio.voiceDuck");
  if (audio.mode === "procedural") {
    ensureNumber(audio.bpm ?? 116, "audio.bpm", 50, 220);
    ensureNumber(audio.seed ?? 1, "audio.seed", 0, 0xffffffff);
  }

  const render = ensureObject(config.render, "render");
  if (![24, 25, 30, 60].includes(render.fps)) throw new PromoError("render.fps must be 24, 25, 30, or 60");
  ensureNumber(render.crf, "render.crf", 0, 40);
  ensureText(render.preset, "render.preset");
  ensureBoolean(render.clean, "render.clean");
  ensureBoolean(render.captioned, "render.captioned");
  if (!render.clean && !render.captioned) throw new PromoError("At least one render variant must be enabled");
  if (!Array.isArray(render.profiles) || !render.profiles.length || render.profiles.length > 4) {
    throw new PromoError("render.profiles must contain 1-4 profiles");
  }
  const profileIds = new Set();
  for (const profile of render.profiles) {
    ensureObject(profile, "render profile");
    const id = ensureText(profile.id, "render profile id");
    if (!/^[a-z0-9][a-z0-9-]{0,31}$/.test(id) || profileIds.has(id)) {
      throw new PromoError(`Invalid or duplicate render profile id: ${id}`);
    }
    profileIds.add(id);
    ensureNumber(profile.width, `profile ${id}.width`, 320, 4096);
    ensureNumber(profile.height, `profile ${id}.height`, 320, 4096);
    if (profile.width % 2 || profile.height % 2) throw new PromoError(`profile ${id} dimensions must be even`);
    if (!new Set(["contain", "cover"]).has(profile.fit)) throw new PromoError(`profile ${id}.fit must be contain or cover`);
  }

  const resolved = {
    config,
    configPath,
    configDir,
    projectName,
    projectRoot,
    outputDir,
    scenes,
    totalDuration,
  };
  return resolved;
}


export async function verifySourceFiles(resolved) {
  const missing = [];
  for (const scene of resolved.scenes) {
    if (scene.sourceFile && !(await exists(scene.sourceFile))) missing.push(`${scene.id}: ${scene.sourceFile}`);
    if (scene.adapterFile && !(await exists(scene.adapterFile))) missing.push(`${scene.id} adapter: ${scene.adapterFile}`);
  }
  if (resolved.config.audio.mode === "file") {
    const audioFile = path.resolve(resolved.configDir, resolved.config.audio.file);
    if (!(await exists(audioFile))) missing.push(`audio.file: ${audioFile}`);
  }
  if (resolved.config.narration.provider === "files") {
    for (let index = 0; index < resolved.config.narration.segments.length; index += 1) {
      const segment = resolved.config.narration.segments[index];
      const file = path.resolve(resolved.configDir, segment.file);
      if (!(await exists(file))) missing.push(`narration segment ${index + 1}: ${file}`);
    }
  }
  if (missing.length) throw new PromoError(`Missing source files:\n${missing.join("\n")}`);
}


export async function writeJson(target, payload) {
  await mkdir(path.dirname(target), { recursive: true });
  await writeFile(target, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}


export function configHash(resolved) {
  return createHash("sha256").update(JSON.stringify(resolved.config)).digest("hex");
}


export async function prepareOutput(resolved, force, preserve = []) {
  await mkdir(resolved.outputDir, { recursive: true });
  const entries = await readdir(resolved.outputDir);
  const marker = path.join(resolved.outputDir, OUTPUT_MARKER);
  const marked = await exists(marker);
  if (entries.length && !marked) {
    throw new PromoError(`Refusing non-empty unmarked output directory: ${resolved.outputDir}`);
  }
  if (entries.length && marked && !force) {
    throw new PromoError(`Output already contains generated files; rerun with --force: ${resolved.outputDir}`);
  }
  if (marked && force) {
    for (const relative of GENERATED_PATHS) {
      if (preserve.includes(relative)) continue;
      const target = path.join(resolved.outputDir, relative);
      if (isInside(resolved.outputDir, target)) await rm(target, { recursive: true, force: true });
    }
  }
  await writeJson(marker, {
    schemaVersion: 1,
    generator: "build-web-promo-video",
    preparedAt: nowIso(),
    configHash: configHash(resolved),
  });
}


export function formatClock(seconds) {
  const total = Math.round(seconds * 1000);
  const minutes = Math.floor(total / 60000);
  const secs = Math.floor((total % 60000) / 1000);
  const millis = total % 1000;
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(millis).padStart(3, "0")}`;
}


export function srtTime(seconds) {
  const total = Math.round(seconds * 1000);
  const hours = Math.floor(total / 3600000);
  const minutes = Math.floor((total % 3600000) / 60000);
  const secs = Math.floor((total % 60000) / 1000);
  const millis = total % 1000;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")},${String(millis).padStart(3, "0")}`;
}


export function assTime(seconds) {
  const centiseconds = Math.round(seconds * 100);
  const hours = Math.floor(centiseconds / 360000);
  const minutes = Math.floor((centiseconds % 360000) / 6000);
  const secs = Math.floor((centiseconds % 6000) / 100);
  const cs = centiseconds % 100;
  return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(cs).padStart(2, "0")}`;
}


export function escapeAssText(text) {
  return text.replace(/\\/g, "\\\\").replace(/\r?\n/g, "\\N").replace(/\{/g, "\\{").replace(/\}/g, "\\}");
}


function commandWorks(command, args) {
  const result = spawnSync(command, args, { encoding: "utf8", windowsHide: true });
  return result.status === 0;
}


export function locateFfmpeg() {
  const candidates = [process.env.FFMPEG_PATH, "ffmpeg"].filter(Boolean);
  for (const candidate of candidates) if (commandWorks(candidate, ["-version"])) return candidate;
  throw new PromoError("FFmpeg not found. Set FFMPEG_PATH or install ffmpeg on PATH.");
}


export function locateFfprobe() {
  const names = process.platform === "win32"
    ? ["ffprobe.exe"]
    : ["ffprobe"];
  const staticCandidates = names.map((name) => path.join(
    SCRIPT_DIR,
    "node_modules",
    "ffprobe-static",
    "bin",
    process.platform === "win32" ? "win32" : process.platform,
    process.arch === "x64" ? "x64" : process.arch,
    name,
  ));
  const sibling = process.env.FFMPEG_PATH && path.isAbsolute(process.env.FFMPEG_PATH)
    ? path.join(path.dirname(process.env.FFMPEG_PATH), names[0])
    : null;
  const candidates = [process.env.FFPROBE_PATH, sibling, "ffprobe", ...staticCandidates].filter(Boolean);
  for (const candidate of candidates) if (commandWorks(candidate, ["-version"])) return candidate;
  throw new PromoError("FFprobe not found. Set FFPROBE_PATH or install ffprobe on PATH.");
}


export function runProcess(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: { ...process.env, ...options.env },
      windowsHide: true,
      stdio: options.capture ? ["ignore", "pipe", "pipe"] : "inherit",
    });
    let stdout = "";
    let stderr = "";
    if (options.capture) {
      child.stdout.on("data", (chunk) => { stdout += chunk; });
      child.stderr.on("data", (chunk) => { stderr += chunk; });
    }
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve({ code, stdout, stderr });
      else reject(new PromoError(`${path.basename(command)} exited with code ${code}${stderr ? `\n${stderr}` : ""}`));
    });
  });
}


export function pythonCommand() {
  return process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
}


export function platformSummary() {
  return { platform: process.platform, arch: process.arch, node: process.version, hostname: os.hostname() };
}
