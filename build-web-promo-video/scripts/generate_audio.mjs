import { copyFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { PromoError, loadProjectConfig, nowIso, parseArgs, writeJson } from "./promo_lib.mjs";


const SAMPLE_RATE = 48000;
const TAU = Math.PI * 2;


function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}


function midi(note) {
  return 440 * 2 ** ((note - 69) / 12);
}


function makeWave(duration, generator) {
  const frames = Math.ceil(duration * SAMPLE_RATE);
  const dataBytes = frames * 4;
  const buffer = Buffer.allocUnsafe(44 + dataBytes);
  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(36 + dataBytes, 4);
  buffer.write("WAVE", 8);
  buffer.write("fmt ", 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(2, 22);
  buffer.writeUInt32LE(SAMPLE_RATE, 24);
  buffer.writeUInt32LE(SAMPLE_RATE * 4, 28);
  buffer.writeUInt16LE(4, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write("data", 36);
  buffer.writeUInt32LE(dataBytes, 40);
  for (let index = 0; index < frames; index += 1) {
    const [left, right] = generator(index / SAMPLE_RATE, index);
    buffer.writeInt16LE(Math.round(clamp(left, -1, 1) * 32767), 44 + index * 4);
    buffer.writeInt16LE(Math.round(clamp(right, -1, 1) * 32767), 46 + index * 4);
  }
  return buffer;
}


function proceduralGenerator(duration, bpm, initialSeed, boundaries) {
  const beat = 60 / bpm;
  const chords = [
    [45, 52, 57, 60],
    [41, 48, 53, 57],
    [48, 55, 60, 64],
    [43, 50, 55, 59],
  ];
  let randomState = initialSeed >>> 0;
  function noise() {
    randomState = (Math.imul(randomState, 1664525) + 1013904223) >>> 0;
    return (randomState / 0xffffffff) * 2 - 1;
  }
  return (time) => {
    const progress = duration ? time / duration : 0;
    const fadeIn = clamp(time / 0.7, 0, 1);
    const fadeOut = clamp((duration - time) / 0.8, 0, 1);
    const energy = (0.72 + 0.22 * Math.sin(Math.PI * clamp(progress, 0, 1))) * fadeIn * fadeOut;
    const beatPosition = time / beat;
    const beatPhase = beatPosition % 1;
    const halfPhase = (beatPosition * 2) % 1;
    const chord = chords[Math.floor(beatPosition / 8) % chords.length];
    let pad = 0;
    for (let voice = 0; voice < chord.length; voice += 1) {
      pad += Math.sin(TAU * midi(chord[voice]) * (1 + (voice - 1.5) * 0.0015) * time + voice * 0.7);
    }
    pad *= 0.035;
    const root = chord[0] - 12;
    const bass = Math.sin(TAU * midi(root) * time) * Math.exp(-beatPhase * 3.2) * 0.16;
    const kickFrequency = 48 + 88 * Math.exp(-beatPhase * 18);
    const kick = Math.sin(TAU * kickFrequency * (beatPhase * beat)) * Math.exp(-beatPhase * 12) * 0.24;
    const arpNote = chord[[0, 1, 2, 1, 3, 2, 1, 2][Math.floor(beatPosition * 4) % 8]] + 12;
    const arpPhase = (beatPosition * 4) % 1;
    const arp = Math.sin(TAU * midi(arpNote) * time) * Math.exp(-arpPhase * 5.5) * 0.075;
    const white = noise();
    const hat = white * Math.exp(-halfPhase * 26) * 0.025;
    let transition = 0;
    for (const boundary of boundaries) {
      const delta = time - boundary;
      if (delta >= -0.35 && delta < 0) transition += white * ((delta + 0.35) / 0.35) ** 2 * 0.08;
      if (delta >= 0 && delta < 0.45) transition += Math.sin(TAU * (78 - delta * 30) * delta) * Math.exp(-delta * 9) * 0.32;
    }
    const pulse = Math.sin(TAU * 0.09 * time) * 0.5 + 0.5;
    const left = (pad * (0.86 + pulse * 0.14) + bass + kick + arp * 0.86 + hat + transition) * energy;
    const right = (pad * (1 - pulse * 0.12) + bass + kick + arp * 1.05 - hat * 0.85 + transition * 0.92) * energy;
    return [Math.tanh(left * 1.3) * 0.78, Math.tanh(right * 1.3) * 0.78];
  };
}


export async function generateAudio(configValue) {
  const resolved = await loadProjectConfig(configValue);
  const audio = resolved.config.audio;
  const targetDir = path.join(resolved.outputDir, "audio");
  await mkdir(targetDir, { recursive: true });
  let target;
  let generated;
  if (audio.mode === "file") {
    const source = path.resolve(resolved.configDir, audio.file);
    target = path.join(targetDir, `music${path.extname(source).toLowerCase() || ".wav"}`);
    await copyFile(source, target);
    generated = false;
  } else {
    target = path.join(targetDir, "music.wav");
    let buffer;
    if (audio.mode === "none") {
      buffer = makeWave(resolved.totalDuration, () => [0, 0]);
    } else {
      let cursor = 0;
      const boundaries = [];
      for (const scene of resolved.scenes.slice(0, -1)) {
        cursor += scene.duration;
        boundaries.push(cursor);
      }
      const generator = proceduralGenerator(
        resolved.totalDuration,
        audio.bpm ?? 116,
        audio.seed ?? 1,
        boundaries,
      );
      buffer = makeWave(resolved.totalDuration, generator);
    }
    await writeFile(target, buffer);
    generated = true;
  }
  const manifest = {
    schemaVersion: 1,
    generatedAt: nowIso(),
    mode: audio.mode,
    file: path.relative(resolved.outputDir, target).replace(/\\/g, "/"),
    generated,
    duration: resolved.totalDuration,
    sampleRate: generated ? SAMPLE_RATE : null,
    channels: generated ? 2 : null,
    bpm: audio.mode === "procedural" ? audio.bpm : null,
    seed: audio.mode === "procedural" ? audio.seed : null,
    musicVolume: audio.musicVolume,
  };
  await writeJson(path.join(targetDir, "manifest.json"), manifest);
  return { resolved, manifest };
}


async function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    const result = await generateAudio(args.config);
    console.log(JSON.stringify({ ok: true, ...result.manifest }, null, 2));
  } catch (error) {
    console.error(JSON.stringify({ ok: false, error: error instanceof PromoError ? error.message : error.stack || String(error) }, null, 2));
    process.exitCode = 2;
  }
}


if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
