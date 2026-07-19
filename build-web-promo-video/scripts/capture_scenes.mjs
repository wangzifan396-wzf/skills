import { createServer } from "node:http";
import { copyFile, mkdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

import { PromoError, loadProjectConfig, nowIso, parseArgs, writeJson } from "./promo_lib.mjs";


const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".gif": "image/gif",
  ".mp3": "audio/mpeg",
  ".wav": "audio/wav",
  ".mp4": "video/mp4",
  ".webm": "video/webm",
};


function inside(parent, child) {
  const relative = path.relative(parent, child);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}


async function startStaticServer(root) {
  const server = createServer(async (request, response) => {
    try {
      const url = new URL(request.url || "/", "http://local");
      if (url.pathname === "/favicon.ico") {
        response.writeHead(204).end();
        return;
      }
      const decoded = decodeURIComponent(url.pathname);
      const relative = decoded === "/" ? "index.html" : decoded.replace(/^\/+/, "");
      let target = path.resolve(root, relative);
      if (!inside(root, target)) {
        response.writeHead(403).end("Forbidden");
        return;
      }
      let info = await stat(target);
      if (info.isDirectory()) {
        target = path.join(target, "index.html");
        info = await stat(target);
      }
      if (!info.isFile()) throw new Error("Not a file");
      const body = await readFile(target);
      response.writeHead(200, {
        "content-type": MIME[path.extname(target).toLowerCase()] || "application/octet-stream",
        "cache-control": "no-store",
        "access-control-allow-origin": "*",
      });
      response.end(body);
    } catch {
      response.writeHead(404).end("Not found");
    }
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  return {
    baseUrl: `http://127.0.0.1:${address.port}`,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}


function sceneUrl(scene, baseUrl) {
  if (scene.sourceType === "url") return scene.source;
  return new URL(scene.source.replace(/^\/+/, ""), `${baseUrl}/`).toString();
}


async function waitUntil(startedAt, targetSeconds) {
  const remaining = Math.round(targetSeconds * 1000 - (performance.now() - startedAt));
  if (remaining > 0) await new Promise((resolve) => setTimeout(resolve, remaining));
}


async function executeAction(page, action) {
  switch (action.type) {
    case "click":
      await page.locator(action.selector).click();
      break;
    case "press":
      if (action.selector) await page.locator(action.selector).press(action.key);
      else await page.keyboard.press(action.key);
      break;
    case "type":
      await page.locator(action.selector).fill(action.text);
      break;
    case "mouseMove":
      await page.mouse.move(action.x, action.y, { steps: action.steps || 1 });
      break;
    case "mouseDown":
      await page.mouse.down({ button: action.button || "left" });
      break;
    case "mouseUp":
      await page.mouse.up({ button: action.button || "left" });
      break;
    case "scroll":
      await page.mouse.wheel(action.deltaX || 0, action.deltaY || 0);
      break;
    case "wait":
      break;
    default:
      throw new PromoError(`Unsupported action: ${action.type}`);
  }
}


export async function captureScenes(configValue) {
  const resolved = await loadProjectConfig(configValue);
  const recordingsDir = path.join(resolved.outputDir, "recordings");
  const temporaryDir = path.join(recordingsDir, ".playwright");
  await mkdir(temporaryDir, { recursive: true });
  const report = {
    schemaVersion: 1,
    generatedAt: nowIso(),
    project: resolved.projectName,
    scenes: [],
    blockers: [],
    warnings: [],
  };

  const browserScenes = resolved.scenes.filter((scene) => scene.sourceType !== "clip");
  let server = null;
  let browser = null;
  let baseUrl = resolved.config.capture.baseUrl || "";
  try {
    if (browserScenes.some((scene) => scene.sourceType === "path") && !baseUrl) {
      server = await startStaticServer(resolved.projectRoot);
      baseUrl = server.baseUrl;
    }
    if (browserScenes.length) {
      let chromium;
      try {
        ({ chromium } = await import("playwright"));
      } catch (error) {
        throw new PromoError(`Playwright is not installed in the Skill scripts directory: ${error.message}`);
      }
      const channel = process.env.PLAYWRIGHT_CHANNEL || resolved.config.capture.browserChannel || undefined;
      try {
        browser = await chromium.launch({
          headless: resolved.config.capture.headless,
          ...(channel ? { channel } : {}),
        });
      } catch (error) {
        throw new PromoError(`Unable to launch Playwright browser. Install Chromium or set PLAYWRIGHT_CHANNEL. ${error.message}`);
      }
    }

    for (const scene of resolved.scenes) {
      if (scene.sourceType === "clip") {
        const extension = path.extname(scene.sourceFile) || ".mp4";
        const target = path.join(recordingsDir, `${scene.id}${extension}`);
        await copyFile(scene.sourceFile, target);
        report.scenes.push({
          id: scene.id,
          sourceType: "clip",
          duration: scene.duration,
          recordings: {
            default: {
              file: path.relative(resolved.outputDir, target).replace(/\\/g, "/"),
              trimStart: Number(scene.clipStart || 0),
            },
          },
          adapter: null,
          pageErrors: [],
          consoleErrors: [],
        });
        continue;
      }

      const targetUrl = sceneUrl(scene, baseUrl);
      const captureTargets = resolved.config.capture.perProfile
        ? resolved.config.render.profiles.map((profile) => ({
            id: profile.id,
            profile,
            viewport: { width: profile.width, height: profile.height },
          }))
        : [{ id: "default", profile: null, viewport: resolved.config.capture.viewport }];
      const reportScene = {
        id: scene.id,
        sourceType: scene.sourceType,
        source: targetUrl,
        duration: scene.duration,
        adapter: scene.adapter || null,
        actions: scene.actions.length,
        recordings: {},
      };

      for (const captureTarget of captureTargets) {
        const contextStarted = performance.now();
        const context = await browser.newContext({
          viewport: captureTarget.viewport,
          recordVideo: {
            dir: temporaryDir,
            size: captureTarget.viewport,
          },
        });
        const page = await context.newPage();
        const pageErrors = [];
        const consoleErrors = [];
        page.on("pageerror", (error) => pageErrors.push(error.message));
        page.on("console", (message) => {
          if (message.type() === "error") consoleErrors.push(message.text());
        });
        try {
          await page.goto(targetUrl, { waitUntil: "load", timeout: 30000 });
          if (resolved.config.capture.postLoadWaitMs) {
            await page.waitForTimeout(resolved.config.capture.postLoadWaitMs);
          }
          if (scene.adapterFile) {
            const module = await import(`${pathToFileURL(scene.adapterFile).href}?v=${Date.now()}`);
            if (typeof module.default !== "function") throw new PromoError(`Adapter must export a default function: ${scene.adapterFile}`);
            await module.default({
              page,
              context,
              scene,
              config: resolved.config,
              baseUrl,
              profile: captureTarget.profile,
            });
          }
          const contentStarted = performance.now();
          for (const action of scene.actions) {
            await waitUntil(contentStarted, action.at);
            await executeAction(page, action);
          }
          await waitUntil(contentStarted, scene.duration);
          const video = page.video();
          await context.close();
          const suffix = captureTarget.id === "default" ? "" : `-${captureTarget.id}`;
          const target = path.join(recordingsDir, `${scene.id}${suffix}.webm`);
          await video.saveAs(target);
          reportScene.recordings[captureTarget.id] = {
            file: path.relative(resolved.outputDir, target).replace(/\\/g, "/"),
            trimStart: (contentStarted - contextStarted) / 1000,
            viewport: captureTarget.viewport,
            pageErrors,
            consoleErrors,
          };
        } catch (error) {
          try { await context.close(); } catch {}
          report.blockers.push({ scene: `${scene.id}/${captureTarget.id}`, message: error.message });
        }
        if (pageErrors.length) {
          report.blockers.push({
            scene: `${scene.id}/${captureTarget.id}`,
            message: `Page errors: ${pageErrors.join(" | ")}`,
          });
        }
        if (consoleErrors.length) {
          report.warnings.push({
            scene: `${scene.id}/${captureTarget.id}`,
            message: `Console errors: ${consoleErrors.join(" | ")}`,
          });
        }
      }
      report.scenes.push(reportScene);
    }
  } finally {
    if (browser) await browser.close();
    if (server) await server.close();
  }

  report.ok = report.blockers.length === 0;
  await writeJson(path.join(recordingsDir, "manifest.json"), {
    schemaVersion: 1,
    generatedAt: nowIso(),
    scenes: report.scenes,
  });
  await writeJson(path.join(resolved.outputDir, "capture-report.json"), report);
  if (!report.ok) throw new PromoError(`Capture failed: ${report.blockers.map((item) => `${item.scene}: ${item.message}`).join("; ")}`);
  return { resolved, report };
}


async function main() {
  try {
    const args = parseArgs(process.argv.slice(2));
    const result = await captureScenes(args.config);
    console.log(JSON.stringify({
      ok: true,
      scenes: result.report.scenes.length,
      warnings: result.report.warnings.length,
      output: path.join(result.resolved.outputDir, "recordings"),
    }, null, 2));
  } catch (error) {
    console.error(JSON.stringify({ ok: false, error: error instanceof PromoError ? error.message : error.stack || String(error) }, null, 2));
    process.exitCode = 2;
  }
}


if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
